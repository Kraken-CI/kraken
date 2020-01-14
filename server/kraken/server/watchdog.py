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

log = logging.getLogger('watchdog')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('watchdog')

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

        timeout = job.timeout if job.timeout else 5 * 60
        duration = now - job.assigned
        if duration > datetime.timedelta(seconds=timeout):
            log.warn('time %ss for job %s expired, canceling', timeout, job)
            job.state = consts.JOB_STATE_COMPLETED
            job.completion_status = consts.JOB_CMPLT_SERVER_TIMEOUT
            job.notes = 'time %ss for job expired' % timeout
            job.executor = None
            # TODO: add canceling the job on executor side
            db.session.commit()
            t = bg_jobs.job_completed.delay(job.id)
            log.info('job %s timed out, bg processing: %s', job, t)


def main():
    app = create_app()

    with app.app_context():

        t0_jobs = time.time()

        while True:
            dt = time.time() - t0_jobs
            if dt > 5:
                _check_jobs()
                t0_jobs = time.time()

            time.sleep(1)


if __name__ == "__main__":
    main()
