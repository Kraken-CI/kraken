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
from sqlalchemy.sql.expression import desc
import clickhouse_driver
import redis
import botocore
import boto3

from . import logs
from .models import db, Agent, AgentsGroup, Run, Job, get_setting
from . import consts
from . import srvcheck
from .. import version
from . import exec_utils
from .bg import jobs as bg_jobs

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


def _check_jobs():
    now = datetime.datetime.utcnow()

    q = Job.query.filter_by(state=consts.JOB_STATE_ASSIGNED)

    for job in q.all():
        if not job.assigned:
            log.warning('job %s assigned but no assign time', job)
            continue

        timeout = job.timeout if job.timeout else consts.DEFAULT_JOB_TIMEOUT
        duration = now - job.assigned
        if duration > datetime.timedelta(seconds=timeout):
            log.warning('time %ss for job %s expired, canceling', timeout, job)
            note = 'time %ss for job expired' % timeout
            exec_utils.cancel_job(job, note, consts.JOB_CMPLT_SERVER_TIMEOUT)


def _check_runs():
    now = datetime.datetime.utcnow()

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


def _check_agents_keep_alive():
    now = datetime.datetime.utcnow()
    five_mins_ago = now - datetime.timedelta(seconds=consts.AGENT_TIMEOUT)

    q = Agent.query
    q = q.filter_by(disabled=False, deleted=None)
    q = q.filter(Agent.last_seen < five_mins_ago)

    for e in q.all():
        e.disabled = True
        e.status_line = 'agent was not seen for last 5 minutes, disabled'
        db.session.commit()
        log.info('agent %s not seen for 5 minutes, disabled', e)


def _destroy_and_delete_if_outdated(agent, ag):
    aws = ag.deployment['aws']
    if aws['destruction_rule'] != consts.DESTRUCTION_RULE_IDLE_TIME:
        return False

    last_job = Job.query.filter_by(agent_used=agent).order_by(desc(Job.finished)).first()
    if not last_job:
        return False

    now = datetime.datetime.utcnow()
    dt = now - last_job.finished
    if dt < datetime.timedelta(seconds=60 * int(aws['idle_time'])):
        return False

    log.info('destroying machine with agent %s due idle time', agent)
    agent.disabled = True
    db.session.commit()
    t = bg_jobs.destroy_machine.delay(agent.id)
    log.info('destroy machine with agent %s, bg processing: %s', agent, t)
    return True


def _delete_if_missing_in_aws(agent, ag):
    if not agent.extra_attrs or 'instance_id' not in agent.extra_attrs:
        return False

    aws = ag.deployment['aws']
    region = aws['region']
    access_key = get_setting('cloud', 'aws_access_key')
    secret_access_key = get_setting('cloud', 'aws_secret_access_key')
    ec2 = boto3.resource('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)

    instance_id = agent.extra_attrs['instance_id']
    try:
        i = ec2.Instance(instance_id)
        i.state
    except Exception:
        agent.deleted = datetime.datetime.utcnow()
        agent.disabled = True
        db.session.commit()
        log.info('deleted dangling agent %d', agent.id)
        return True

    return False


def _check_agents_to_destroy():
    q = Agent.query.filter_by(deleted=None, job=None)
    q = q.join('agents_groups', 'agents_group')
    q = q.filter_by(deleted=None)
    q = q.filter(AgentsGroup.deployment.isnot(None))

    outdated_count = 0
    dangling_count = 0
    for agent in q.all():
        ag = agent.agents_groups[0].agents_group
        if ag.deployment['method'] != consts.AGENT_DEPLOYMENT_METHOD_AWS or 'aws' not in ag.deployment or not ag.deployment['aws']:
            continue

        deleted = _destroy_and_delete_if_outdated(agent, ag)
        if deleted:
            outdated_count += 1
            continue

        deleted = _delete_if_missing_in_aws(agent, ag)
        if deleted:
            dangling_count += 1
            continue

    if outdated_count > 0:
        log.info('destroyed and deleted %d aws ec2 instances and agents', outdated_count)
    if dangling_count > 0:
        log.info('deleted %d dangling agents without any aws ec2 instance', dangling_count)


def _check_machines_with_no_agent():
    access_key = get_setting('cloud', 'aws_access_key')
    secret_access_key = get_setting('cloud', 'aws_secret_access_key')

    q = AgentsGroup.query
    q = q.filter_by(deleted=None)
    q = q.filter(AgentsGroup.deployment.isnot(None))

    count = 0
    for ag in q.all():
        if ag.deployment['method'] != consts.AGENT_DEPLOYMENT_METHOD_AWS or 'aws' not in ag.deployment or not ag.deployment['aws']:
            continue

        aws = ag.deployment['aws']
        region = aws['region']
        ec2 = boto3.resource('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)

        now = datetime.datetime.utcnow()

        try:
            instances = ec2.instances.filter(Filters=[{'Name': 'tag:kraken-group', 'Values': ['%d' % ag.id]}])
            instances = list(instances)
        except Exception:
            log.exception()
            continue

        for i in instances:
            # if terminated then skip it
            if i.state['Name'] == 'terminated':
                continue

            # if assigned to some agent then skip it
            assigned = False
            for aa in ag.agents:
                agent = aa.agent
                if agent.extra_attrs and 'instance_id' in agent.extra_attrs and agent.extra_attrs['instance_id'] == i.id:
                    assigned = True
                    break
            if assigned:
                continue

            # instances have to be old enough to avoid race condition with
            # case when instances are being created but not yet assigned to agents
            if now - i.launch_time < datetime.timedelta(minutes=10):
                continue

            # the instance is not terminated, not assigned, old enough
            # so delete it as it seems to be a lost instance
            log.info('terminating lost aws ec2 instance %s', i.id)
            try:
                i.terminate()
            except Exception:
                log.exception('IGNORED EXCEPTION')

            count += 1

    if count > 0:
        log.info('terminated %d lost aws ec2 instances', count)


def _check_agents():
    _check_agents_keep_alive()
    _check_agents_to_destroy()
    _check_machines_with_no_agent()


def _check_for_errors_in_logs():
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    now = datetime.datetime.utcnow()
    start_date = now - datetime.timedelta(hours=1)

    query = "select count(*) from logs where level = 'ERROR' and time > %(start_date)s;"
    rows = ch.execute(query, {'start_date': start_date})
    errors_count = rows[0][0]

    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    rds = redis.Redis(host=redis_addr, port=6379, db=1)

    rds.set('error-logs-count', errors_count)
    #log.info('updated errors count to %s', errors_count)


def main():
    app = create_app()

    with app.app_context():

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


if __name__ == "__main__":
    main()
