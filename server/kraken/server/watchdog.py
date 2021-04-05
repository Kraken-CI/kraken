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

from . import logs
from .models import db, Agent, Run, Job, get_setting
from . import consts
from . import srvcheck
from .. import version
from . import exec_utils

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


def _check_agents():
    now = datetime.datetime.utcnow()
    five_mins_ago = now - datetime.timedelta(seconds=consts.AGENT_TIMEOUT)

    q = Agent.query
    q = q.filter_by(disabled=False, deleted=None)
    q = q.filter(Agent.last_seen < five_mins_ago)

    for e in q.all():
        e.disable = True
        e.status_line = 'agent was not seen for last 5 minutes, disabled'
        db.session.commit()
        log.info('agent %s not seen for 5 minutes, disabled', e)


def main():
    app = create_app()

    with app.app_context():

        t0_jobs = t0_runs = t0_agents = time.time()

        while True:
            # check jobs every 5 seconds
            dt = time.time() - t0_jobs
            if dt > 5:
                _check_jobs()
                t0_jobs = time.time()

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
