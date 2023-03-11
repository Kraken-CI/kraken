#!/usr/bin/env python3

# Copyright 2020 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
import logging
import datetime

from flask import Flask
from sqlalchemy.sql.expression import asc, desc, cast, or_
from sqlalchemy import Integer, func
import redis

from . import logs
from .models import db, Agent, AgentsGroup, Run, Job, get_setting
from .models import Branch
from .bg import jobs as bg_jobs
from .cloud import cloud
from . import consts
from . import srvcheck
from .. import version
from . import exec_utils
from . import kkrq
from . import utils
from . import dbutils
from . import chops

log = logging.getLogger('watchdog')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.wait_for_service('planner', planner_url, 7997)

    logs.setup_logging('watchdog')
    log.info('Kraken Watchdog started, version %s', version.version)

    # Create  Flask app instance
    app = Flask('Kraken Watchdog')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url + '?application_name=watchdog'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    # setup sentry
    with app.app_context():
        sentry_url = get_setting('monitoring', 'sentry_dsn')
        logs.setup_sentry(sentry_url)

    return app


def _exc_handler_with_db_rollback(fnc):
    def inner_function(*args, **kwargs):
        try:
            return fnc(*args, **kwargs)
        except Exception:
            log.exception('IGNORED EXCEPTION')
            db.session.rollback()
            time.sleep(10)
        return None
    return inner_function


@_exc_handler_with_db_rollback
def _check_jobs_if_expired():
    now = utils.utcnow()

    q = Job.query.filter_by(state=consts.JOB_STATE_ASSIGNED)

    job_count = 0
    canceled_count = 0

    for job in q.all():
        log.set_ctx(branch=job.run.flow.branch_id, flow_kind=job.run.flow.kind, flow=job.run.flow_id, run=job.run.id, job=job.id)

        job_count += 1
        if not job.assigned:
            log.warning('job %s assigned but no assign time', job)
            log.reset_ctx()
            continue

        timeout = job.timeout if job.timeout else consts.DEFAULT_JOB_TIMEOUT
        duration = now - job.assigned
        if duration > datetime.timedelta(seconds=timeout):
            log.warning('time %ss for job %s expired, canceling', timeout, job)
            note = 'job expired after %ss' % timeout
            exec_utils.cancel_job(job, note, consts.JOB_CMPLT_SERVER_TIMEOUT)
            canceled_count += 1

        log.reset_ctx()

    if job_count > 0:
        log.info('canceled jobs:%d / all:%d', canceled_count, job_count)


@_exc_handler_with_db_rollback
def _check_jobs_if_missing_agents():
    groups_jobs = {}  # keep here groups that are needed and one, any job

    q = Job.query.filter_by(covered=False, deleted=None, state=consts.JOB_STATE_QUEUED)
    for job in q.all():
        ag = job.agents_group
        if (ag.deployment and
            ag.deployment['method'] in [consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                                        consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE,
                                        consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM,
                                        consts.AGENT_DEPLOYMENT_METHOD_K8S,
                                        ]):
            groups_jobs[ag.id] = job.id

    for ag_id in groups_jobs:
        kkrq.enq_neck(bg_jobs.spawn_new_agents, ag_id)
    if groups_jobs:
        n = len(groups_jobs)
        grps = list(groups_jobs.keys())[:5]
        job = groups_jobs.popitem()[1]
        log.info('enqueued spawning new agents for %d groups eg:%s with no agents but with waiting jobs, eg: %s',
                 n, grps, job)


def _check_jobs():
    _check_jobs_if_expired()
    _check_jobs_if_missing_agents()


@_exc_handler_with_db_rollback
def _check_runs_timeout():
    now = utils.utcnow()

    q = Run.query.filter_by(finished=None)
    q = q.filter(Run.state != consts.RUN_STATE_MANUAL)  # TODO: manual runs will require timeouting as well when jobs are started

    for run in q.all():
        timeout = run.stage.schema.get('timeout', consts.DEFAULT_RUN_TIMEOUT)
        if run.started:
            begin = run.started
        else:
            begin = run.created
        end_time = begin + datetime.timedelta(seconds=timeout)
        if end_time > now:
            # no timeout yet
            continue

        log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

        note = 'run %s timed out, deadline was: %s' % (run, str(end_time))
        log.info(note)
        run.note = note

        # cancel any pending jobs
        canceled_jobs_count = 0
        for job in run.jobs:
            if job.state != consts.JOB_STATE_COMPLETED:
                exec_utils.cancel_job(job, note, consts.JOB_CMPLT_SERVER_TIMEOUT)
                canceled_jobs_count += 1

        # if there is no pending jobs then complete run now
        if canceled_jobs_count == 0:
            exec_utils.complete_run(run, now)

        log.reset_ctx()


@_exc_handler_with_db_rollback
def _check_runs_missing_history_analysis():
    now = utils.utcnow()
    three_months = now - datetime.timedelta(days=90)
    twenty_mins = now - datetime.timedelta(minutes=20)

    q = Run.query.filter(Run.finished > three_months)
    q = q.filter(Run.finished < twenty_mins)
    q = q.filter(Run.state != consts.RUN_STATE_PROCESSED)
    q = q.order_by(asc(Run.finished))

    visited_branches = set()
    for run in q.all():
        if run.flow.branch_id in visited_branches:
            continue

        log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

        log.info('run with missing history %s', run)
        visited_branches.add(run.flow.branch_id)
        kkrq.enq_neck(bg_jobs.analyze_results_history, run.id)

        log.reset_ctx()


def _check_runs():
    _check_runs_timeout()
    _check_runs_missing_history_analysis()


def _cancel_job_and_unassign_agent(agent):
    exec_utils.cancel_job(agent.job, 'agent not alive', consts.JOB_CMPLT_AGENT_NOT_ALIVE)
    job = agent.job
    agent.job = None
    job.agent = None
    db.session.commit()


@_exc_handler_with_db_rollback
def _check_agents_keep_alive():
    now = utils.utcnow()
    five_mins_ago = now - datetime.timedelta(seconds=consts.AGENT_TIMEOUT)
    ten_mins_ago = now - datetime.timedelta(seconds=consts.SLOW_AGENT_TIMEOUT)

    q = Agent.query
    q = q.filter_by(disabled=False, deleted=None)
    q = q.filter(Agent.last_seen < five_mins_ago)

    for a in q.all():
        log.reset_ctx()
        log.set_ctx(agent=a.id)
        # in case of cloud machines check for 10mins, not 5mins
        ag = dbutils.find_cloud_assignment_group(a)
        if (ag and
            ag.deployment['method'] in [consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                                        consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE,
                                        consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM,
                                        consts.AGENT_DEPLOYMENT_METHOD_K8S]):
            if a.last_seen > ten_mins_ago:
                continue

        a.disabled = True
        a.status_line = 'agent was not seen for last 5 minutes, disabled'
        log.info('agent %s not seen for 5 minutes, disabled', a)
        db.session.commit()

        if a.job:
            _cancel_job_and_unassign_agent(a)


def _destroy_and_delete_if_outdated(agent, depl, method):
    destroy = False

    if method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
        # if for some reason k8s pod still exists after completing the job
        # then destroy it after 3 mins
        destruction_after_time = 3
    else:
        if 'destruction_after_time' in depl:
            destruction_after_time = int(depl['destruction_after_time'])
        else:
            destruction_after_time = 10  # default if somehow not set

    # check if idle time after job passed, then destroy VM
    if destruction_after_time > 0:
        max_idle_time = datetime.timedelta(seconds=60 * destruction_after_time)

        q = Job.query.filter_by(agent_used=agent)
        q = q.filter(Job.finished.isnot(None))
        q = q.filter(Job.finished > agent.created)
        q = q.order_by(desc(Job.finished))
        last_job = q.first()
        now = utils.utcnow()
        if last_job:
            dt = now - last_job.finished
            if dt >= max_idle_time:
                log.info('agent: %s, timed out %s > %s - destroying it, last job %s',
                         agent, dt, max_idle_time, last_job)
                destroy = True
            else:
                log.info('agent: %s, not yet timed out %s < %s - skipped', agent, dt, max_idle_time)
        elif now - agent.created >= max_idle_time:
            log.info('agent: %s, timed out %s - destroying it, created at %s vs now %s', agent, max_idle_time, agent.created, now)
            destroy = True
        else:
            log.info('agent: %s, no last job and not idle enough - skipped', agent)
    else:
        log.info('agent: %s, destruction_after_time is 0 - skipped', agent)

    # check if number of executed jobs on VM is reached, then destroy VM
    if not destroy:
        if 'destruction_after_jobs' in depl and int(depl['destruction_after_jobs']) > 0:
            max_jobs = int(depl['destruction_after_jobs'])
            q = Job.query.filter_by(agent_used=agent, state=consts.JOB_STATE_COMPLETED)
            q = q.filter(Job.finished > agent.created)
            jobs_num = q.count()
            if jobs_num >= max_jobs:
                log.info('agent: %s, max jobs reached %d/%d', agent, jobs_num, max_jobs)
                # TODO: remove it later, for debugging only
                #for j in q.all():
                #    log.info('  job: %s', j)
                destroy = True
            else:
                log.info('agent: %s, max jobs not reached yet %d/%d - skipped', agent, jobs_num, max_jobs)
        else:
            log.info('agent: %s, destruction_after_jobs is 0 - skipped', agent)

    # if machine mark for destruction then schedule it
    if destroy:
        log.info('disabling and destroying machine with agent %s', agent)
        agent.disabled = True
        db.session.commit()
        kkrq.enq(bg_jobs.destroy_machine, agent.id)
        return True

    return False


def _delete_if_missing_in_cloud(ag, agent):
    if not agent.extra_attrs or 'instance_id' not in agent.extra_attrs:
        log.warning('agent:%d, no instance id in extra_attrs', agent.id)
        return False

    exists = True
    try:
        exists = cloud.check_if_machine_exists(ag, agent)
    except Exception:
        pass

    if not exists:
        dbutils.delete_agent(agent)
        log.info('deleted dangling agent %s', agent)
        return True

    return False


@_exc_handler_with_db_rollback
def _check_agents_to_destroy():
    # look for agents that are not deleted, still available for use ie. authorized
    # and without currently running job
    # that have some deployment method configured
    q = Agent.query.filter_by(deleted=None, authorized=True, job=None)
    q = q.join('agents_groups', 'agents_group')
    q = q.filter(AgentsGroup.deployment.isnot(None))
    # TODO ECS
    q = q.filter(or_(cast(AgentsGroup.deployment['method'], Integer) == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                     cast(AgentsGroup.deployment['method'], Integer) == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM,
                     cast(AgentsGroup.deployment['method'], Integer) == consts.AGENT_DEPLOYMENT_METHOD_K8S))

    outdated_count = 0
    dangling_count = 0
    all_count = 0
    for agent in q.all():
        log.reset_ctx()
        log.set_ctx(agent=agent.id)

        all_count += 1
        ag = dbutils.find_cloud_assignment_group(agent)

        if not ag:
            log.error('missing ag in agent %s', agent)
            continue

        if not ag.deployment:
            log.error('missing deployment in ag %s', ag)
            continue

        method = consts.AGENT_DEPLOYMENT_METHOD_MANUAL
        try:
            method, depl = ag.get_deployment()
        except Exception:
            pass
        if method not in [consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                          consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM,
                          consts.AGENT_DEPLOYMENT_METHOD_K8S]:
            log.error('unsupported deployment method %s', ag.deployment['method'])
            continue
        deleted = _destroy_and_delete_if_outdated(agent, depl, method)
        if deleted:
            outdated_count += 1
            if agent.job:
                _cancel_job_and_unassign_agent(agent)
            continue

        deleted = _delete_if_missing_in_cloud(ag, agent)
        if deleted:
            dangling_count += 1
            if agent.job:
                _cancel_job_and_unassign_agent(agent)
            continue

    log.reset_ctx()

    if outdated_count > 0:
        log.info('all agents:%d, destroyed and deleted %d VM instances and agents',
                 all_count, outdated_count)
    if dangling_count > 0:
        log.info('deleted %d dangling agents without any VM instance', dangling_count)

    return all_count, outdated_count, dangling_count


@_exc_handler_with_db_rollback
def _check_machines_with_no_agent():
    # look for AWS EC2 or Azure VM machines that do not have agents in database
    # and destroy such machines
    q = AgentsGroup.query
    q = q.filter_by(deleted=None)
    q = q.filter(AgentsGroup.deployment.isnot(None))

    all_groups = 0
    aws_ec2_groups = 0
    azure_vm_groups = 0
    k8s_groups = 0

    for ag in q.all():
        all_groups += 1

        if ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
            aws_ec2_groups += 1
        elif ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
            azure_vm_groups += 1
        elif ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_K8S:
            k8s_groups += 1
        else:
            continue

        counts = cloud.cleanup_dangling_machines(ag)

        instances = counts[0]
        terminated_instances = counts[1]
        assigned_instances = counts[2]
        orphaned_instances = counts[3]
        orphaned_terminated_instances = counts[4]

        if (instances + terminated_instances + assigned_instances +
            orphaned_instances + orphaned_terminated_instances > 0):
            log.info('group: %s, instances:%d, already-terminated:%d, still-assigned:%d, orphaned:%d, terminated-orphaned:%d',
                     ag,
                     instances,
                     terminated_instances,
                     assigned_instances,
                     orphaned_instances,
                     orphaned_terminated_instances)
    if aws_ec2_groups + azure_vm_groups + k8s_groups > 0:
        log.info('machines with no agent by groups: aws:%d, azure vm:%d, k8s:%d / all:%d',
                 aws_ec2_groups, azure_vm_groups, k8s_groups, all_groups)


@_exc_handler_with_db_rollback
def _check_agents_counts():
    q = db.session.query(Agent.authorized, func.count(Agent.authorized))
    q = q.filter_by(deleted=None)
    q = q.group_by(Agent.authorized)
    counts = q.all()

    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_KRAKEN_DB)

    for authorized, cnt in counts:
        if authorized:
            rds.set('authorized-agents', cnt)
        else:
            rds.set('non-authorized-agents', cnt)


def _check_agents():
    _check_agents_keep_alive()
    _check_agents_to_destroy()
    _check_machines_with_no_agent()
    _check_agents_counts()


@_exc_handler_with_db_rollback
def _check_for_errors_in_logs():
    ch = chops.get_clickhouse()

    now = utils.utcnow()
    start_date = now - datetime.timedelta(hours=1)

    query = "select count(*) from logs where level = 'ERROR' and time > %(start_date)s;"
    rows = ch.execute(query, {'start_date': start_date})
    errors_count = rows[0][0]

    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_KRAKEN_DB)

    rds.set('error-logs-count', errors_count)
    #log.info('updated errors count to %s', errors_count)


@_exc_handler_with_db_rollback
def _run_branch_retention_policy():
    log.info('branches logs retention')
    ch = chops.get_clickhouse()

    q = Branch.query
    q = q.filter_by(deleted=None)

    for branch in q.all():
        log.reset_ctx()
        log.set_ctx(branch=branch.id)

        if branch.retention_policy:
            rp = branch.retention_policy
            months = [rp['ci_logs'], rp['dev_logs']]
        else:
            months = [6, 3]

        for flow_kind in [0, 1]:
            query = "ALTER TABLE logs DELETE WHERE branch = %(branch_id)s AND flow_kind = %(flow_kind)s AND time < (now() - toIntervalMonth(%(months)s))"
            params = dict(branch_id=branch.id,
                          flow_kind=flow_kind,
                          months=months[flow_kind])
            resp = ch.execute(query, params)
            log.info('deleted logs %s', resp)
            # TODO: trace number of deleted logs

    log.reset_ctx()


def _main_loop():
    t0 = time.time()
    t0_log_errs = t0_jobs = t0_runs = t0_agents = t0
    t0_branch_retention_policy = t0


    while True:
        # check jobs every 5 seconds
        dt = time.time() - t0_jobs
        if dt > 5:
            _check_jobs()
            t0_jobs = time.time()

        # check for error in logs every 15 seconds
        dt = time.time() - t0_log_errs
        if dt > 15:
            _check_for_errors_in_logs()
            t0_log_errs = time.time()

        # check runs every 30 seconds
        dt = time.time() - t0_runs
        if dt > 30:
            _check_runs()
            t0_runs = time.time()

        # check agents every 30 seconds
        dt = time.time() - t0_agents
        if dt > 30:
            _check_agents()
            t0_agents = time.time()

        # run retention policy every 24 h
        dt = time.time() - t0_branch_retention_policy
        if dt > 60 * 60 * 24:
            _run_branch_retention_policy()
            t0_branch_retention_policy = time.time()

        time.sleep(1)

def main():
    app = create_app()

    with app.app_context():
        while True:
            try:
                _main_loop()
            except Exception:
                log.exception('IGNORED EXCEPTION')
                db.session.rollback()
                time.sleep(10)


if __name__ == "__main__":
    main()
