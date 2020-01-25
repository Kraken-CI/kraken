#!/usr/bin/env python3
import os
import time
import logging
import datetime

from flask import Flask
from sqlalchemy.sql.expression import asc, desc, func, cast

from . import logs
from .models import db, Executor, Run, Job
from . import consts
from . import srvcheck
from .bg import jobs as bg_jobs
from . import execution

log = logging.getLogger('watchdog')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('watchdog')
    log.info('Kraken Watchdog started')

    # Create  Flask app instance
    app = Flask('Kraken Watchdog')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    return app


def _check_jobs():
    now = datetime.datetime.utcnow()

    q = Job.query.filter_by(state=consts.JOB_STATE_ASSIGNED)

    for job in q.all():
        if not job.assigned:
            log.warn('job %s assigned but no assign time', job)
            continue

        timeout = job.timeout if job.timeout else consts.DEFAULT_JOB_TIMEOUT
        duration = now - job.assigned
        if duration > datetime.timedelta(seconds=timeout):
            log.warn('time %ss for job %s expired, canceling', timeout, job)
            note = 'time %ss for job expired' % timeout
            execution.cancel_job(job, note=note)


def _check_runs():
    now = datetime.datetime.utcnow()

    q = Run.query.filter_by(state=consts.RUN_STATE_IN_PROGRESS)

    for run in q.all():
        timeout = run.stage.schema.get('timeout', consts.DEFAULT_RUN_TIMEOUT)
        end_time = run.started + datetime.timedelta(seconds=timeout)
        if end_time > now:
            continue
        note = 'run %s timed out, deadline was: %s' % (str(run), str(end_time))
        log.info(note)
        run.note = note
        for job in run.jobs:
            execution.cancel_job(job, note=note)


def _check_executors():
    now = datetime.datetime.utcnow()
    five_mins_ago = now - datetime.timedelta(seconds=consts.EXECUTOR_TIMEOUT)

    q = Executor.query
    q = q.filter_by(disabled=False)
    q = q.filter(Executor.last_seen < five_mins_ago)

    for e in q.all():
        e.disable = True
        e.status_line = 'executor was not seen for last 5 minutes, disabled'
        db.session.commit()
        log.info('executor %s not seen for 5 minutes, disabled', e)


def main():
    app = create_app()

    with app.app_context():

        t0_jobs = t0_runs = t0_executors = time.time()

        while True:
            # check jobs
            dt = time.time() - t0_jobs
            if dt > 5:
                _check_jobs()
                t0_jobs = time.time()

            # check runs
            dt = time.time() - t0_runs
            if dt > 30:
                _check_runs()
                t0_runs = time.time()

            # check executors
            dt = time.time() - t0_executors
            if dt > 30:
                _check_executors()
                t0_executors = time.time()

            time.sleep(1)


if __name__ == "__main__":
    main()
