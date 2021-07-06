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
from urllib.parse import urlparse

from flask import Flask
from sqlalchemy.sql.expression import desc, cast
from sqlalchemy import Integer
import clickhouse_driver
import redis
import boto3
import pytz

from . import logs
from .models import db, Agent, AgentsGroup, Run, Job, get_setting
from . import consts
from . import srvcheck
from .. import version
from . import exec_utils
from .bg import jobs as bg_jobs
from . import kkrq
from . import utils

log = logging.getLogger('watchdog')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

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


def _check_jobs_if_expired():
    now = utils.utcnow()

    q = Job.query.filter_by(state=consts.JOB_STATE_ASSIGNED)

    job_count = 0
    canceled_count = 0

    for job in q.all():
        job_count += 1
        if not job.assigned:
            log.warning('job %s assigned but no assign time', job)
            continue

        timeout = job.timeout if job.timeout else consts.DEFAULT_JOB_TIMEOUT
        duration = now - job.assigned
        if duration > datetime.timedelta(seconds=timeout):
            log.warning('time %ss for job %s expired, canceling', timeout, job)
            note = 'job expired after %ss' % timeout
            exec_utils.cancel_job(job, note, consts.JOB_CMPLT_SERVER_TIMEOUT)
            canceled_count += 1

    log.info('canceled jobs:%d / all:%d', canceled_count, job_count)


def _check_jobs_if_missing_agents():
    groups = set()
    q = Job.query.filter_by(covered=False, deleted=None, state=consts.JOB_STATE_QUEUED)
    for job in q.all():
        ag = job.agents_group
        if ag.deployment and ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AWS and 'aws' in ag.deployment:
            groups.add(ag.id)

    for ag_id in groups:
        kkrq.enq_neck(bg_jobs.spawn_new_agents, ag_id)


def _check_jobs():
    _check_jobs_if_expired()
    _check_jobs_if_missing_agents()


def _check_runs():
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
        note = 'run %d timed out, deadline was: %s' % (run.id, str(end_time))
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


def _cancel_job_and_unassign_agent(agent):
    exec_utils.cancel_job(agent.job, 'agent not alive', consts.JOB_CMPLT_AGENT_NOT_ALIVE)
    job = agent.job
    agent.job = None
    job.agent = None
    db.session.commit()


def _check_agents_keep_alive():
    now = utils.utcnow()
    five_mins_ago = now - datetime.timedelta(seconds=consts.AGENT_TIMEOUT)
    ten_mins_ago = now - datetime.timedelta(seconds=consts.SLOW_AGENT_TIMEOUT)

    q = Agent.query
    q = q.filter_by(disabled=False, deleted=None)
    q = q.filter(Agent.last_seen < five_mins_ago)

    for a in q.all():
        # in case of AWS VMs check for 10mins, not 5mins
        for aa in a.agents_groups:
            ag = aa.agents_group
            if ag.deployment and ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AWS and 'aws' in ag.deployment:
                if a.last_seen > ten_mins_ago:
                    continue

        a.disabled = True
        a.status_line = 'agent was not seen for last 5 minutes, disabled'
        log.info('agent %s not seen for 5 minutes, disabled', a)
        db.session.commit()

        if a.job:
            _cancel_job_and_unassign_agent(a)


def _destroy_and_delete_if_outdated(agent, ag):
    aws = ag.deployment['aws']

    destroy = False

    # check if idle time after job passed, then destroy VM
    if 'destruction_after_time' in aws and int(aws['destruction_after_time']) > 0:
        q = Job.query.filter_by(agent_used=agent)
        q = q.filter(Job.finished.isnot(None))
        q = q.order_by(desc(Job.finished))
        last_job = q.first()
        if last_job:
            now = utils.utcnow()
            dt = now - last_job.finished
            timeout = datetime.timedelta(seconds=60 * int(aws['destruction_after_time']))
            if dt >= timeout:
                log.info('agent:%d, timed out %d > %d - destroying it', agent.id, dt, timeout)
                destroy = True
            else:
                log.info('agent:%d, not yet timed out %d < %d - skipped', agent.id, dt, timeout)
        else:
            log.info('agent:%d, no last job - skipped', agent.id)
    else:
        log.info('agent:%d, destruction_after_time is 0 - skipped', agent.id)

    # check if number of executed jobs on VM is reached, then destroy VM
    if not destroy and 'destruction_after_jobs' in aws and int(aws['destruction_after_jobs']) > 0:
        max_jobs = int(aws['destruction_after_jobs'])
        jobs_num = Job.query.filter_by(agent_used=agent, state=consts.JOB_STATE_COMPLETED).count()
        if jobs_num >= max_jobs:
            log.info('agent:%d, max jobs reached %d/%d', agent.id, jobs_num, max_jobs)
            destroy = True
        else:
            log.info('agent:%d, max jobs not reached yet %d/%d - skipped', agent.id, jobs_num, max_jobs)
    else:
        log.info('agent:%d, destruction_after_jobs is 0 - skipped', agent.id)

    # if machine mark for destruction then schedule it
    if destroy:
        log.info('disabling and destroying machine with agent %s', agent)
        agent.disabled = True
        db.session.commit()
        kkrq.enq(bg_jobs.destroy_machine, agent.id)
        return True

    return False


def _delete_if_missing_in_aws(agent, ag):
    if not agent.extra_attrs or 'instance_id' not in agent.extra_attrs:
        log.warning('agent:%d, no instance id in extra_attrs', agent.id)
        return False

    aws = ag.deployment['aws']
    region = aws['region']
    access_key = get_setting('cloud', 'aws_access_key')
    secret_access_key = get_setting('cloud', 'aws_secret_access_key')
    ec2 = boto3.resource('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)

    instance_id = agent.extra_attrs['instance_id']
    try:
        # try to get instance, if missing then raised exception will cause deleting agent
        i = ec2.Instance(instance_id)
        i.state  # pylint: disable=pointless-statement
        if i.state['Name'] == 'terminated':
            # if instance exists but is terminated also trigger deleting agent by raising an exception
            raise Exception('terminated')
    except Exception:
        agent.deleted = utils.utcnow()
        agent.disabled = True
        db.session.commit()
        log.info('deleted dangling agent %d', agent.id)
        return True

    return False


def _check_agents_to_destroy():
    q = Agent.query.filter_by(deleted=None)
    q = q.join('agents_groups', 'agents_group')
    q = q.filter(cast(AgentsGroup.deployment['method'], Integer) == consts.AGENT_DEPLOYMENT_METHOD_AWS)

    outdated_count = 0
    dangling_count = 0
    all_count = 0
    for agent in q.all():
        all_count += 1
        ag = agent.agents_groups[0].agents_group

        deleted = _destroy_and_delete_if_outdated(agent, ag)
        if deleted:
            outdated_count += 1
            if agent.job:
                _cancel_job_and_unassign_agent(agent)
            continue

        deleted = _delete_if_missing_in_aws(agent, ag)
        if deleted:
            dangling_count += 1
            if agent.job:
                _cancel_job_and_unassign_agent(agent)
            continue

    log.info('all agents:%d, destroyed and deleted %d aws ec2 instances and agents',
             all_count, outdated_count)
    log.info('deleted %d dangling agents without any aws ec2 instance', dangling_count)

    return all_count, outdated_count, dangling_count


def _check_machines_with_no_agent():
    # look for AWS EC2 machines that do not have agents in database
    # and destroy such machines
    access_key = get_setting('cloud', 'aws_access_key')
    secret_access_key = get_setting('cloud', 'aws_secret_access_key')

    q = AgentsGroup.query
    q = q.filter_by(deleted=None)
    q = q.filter(AgentsGroup.deployment.isnot(None))

    all_groups = 0
    aws_groups = 0

    for ag in q.all():
        all_groups += 1
        if not ag.deployment or ag.deployment['method'] != consts.AGENT_DEPLOYMENT_METHOD_AWS or 'aws' not in ag.deployment or not ag.deployment['aws']:
            continue

        aws_groups += 1

        aws = ag.deployment['aws']
        region = aws['region']
        ec2 = boto3.resource('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)

        now = utils.utcnow()

        try:
            instances = ec2.instances.filter(Filters=[{'Name': 'tag:kraken-group', 'Values': ['%d' % ag.id]}])
            instances = list(instances)
        except Exception:
            log.exception('IGNORED EXCEPTION')
            continue

        ec2_instances = 0
        ec2_terminated_instances = 0
        ec2_assigned_instances = 0
        ec2_orphaned_instances = 0
        ec2_orphaned_terminated_instances = 0

        for i in instances:
            ec2_instances += 1
            # if terminated then skip it
            if i.state['Name'] == 'terminated':
                ec2_terminated_instances += 1
                continue

            # if assigned to some agent then skip it
            assigned = False
            for aa in ag.agents:
                agent = aa.agent
                if agent.extra_attrs and 'instance_id' in agent.extra_attrs and agent.extra_attrs['instance_id'] == i.id:
                    assigned = True
                    break
            if assigned:
                ec2_assigned_instances += 1
                continue

            # instances have to be old enough to avoid race condition with
            # case when instances are being created but not yet assigned to agents
            lt = i.launch_time.replace(tzinfo=pytz.utc)
            if now - lt < datetime.timedelta(minutes=10):
                continue

            # the instance is not terminated, not assigned, old enough
            # so delete it as it seems to be a lost instance
            log.info('terminating lost aws ec2 instance %s', i.id)
            ec2_orphaned_instances += 1
            try:
                i.terminate()
            except Exception:
                log.exception('IGNORED EXCEPTION')

            ec2_orphaned_terminated_instances += 1

        log.info('group:%d, aws ec2 instances:%d, already-terminated:%d, still-assigned:%d, orphaned:%d, terminated-orphaned:%d',
                 ag.id,
                 ec2_instances,
                 ec2_terminated_instances,
                 ec2_assigned_instances,
                 ec2_orphaned_instances,
                 ec2_orphaned_terminated_instances)
    log.info('aws groups:%d / all:%d', aws_groups, all_groups)


def _check_agents():
    _check_agents_keep_alive()
    _check_agents_to_destroy()
    _check_machines_with_no_agent()


def _check_for_errors_in_logs():
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    now = utils.utcnow()
    start_date = now - datetime.timedelta(hours=1)

    query = "select count(*) from logs where level = 'ERROR' and time > %(start_date)s;"
    rows = ch.execute(query, {'start_date': start_date})
    errors_count = rows[0][0]

    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    rds = redis.Redis(host=redis_addr, port=6379, db=consts.REDIS_KRAKEN_DB)

    rds.set('error-logs-count', errors_count)
    #log.info('updated errors count to %s', errors_count)


def _main_loop():
    t0_log_errs = t0_jobs = t0_runs = t0_agents = time.time()

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
