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

log = logging.getLogger('scheduler')


def assign_jobs_to_executors():
    counter = 0

    all_idle_executors = Executor.query.filter_by(job=None).all()
    executors_count = len(all_idle_executors)
    if executors_count == 0:
        return 0
    idle_executors_by_group = {}
    for e in all_idle_executors:
        for asm in e.executor_groups:
            grp_id = asm.executor_group_id
            if grp_id not in idle_executors_by_group:
                idle_executors_by_group[grp_id] = []
            idle_executors_by_group[grp_id].append(e)

    q = Job.query.filter_by(state=consts.JOB_STATE_QUEUED, executor_used=None)
    q = q.join('run')
    waiting_jobs = q.order_by(asc(Run.created), asc(Job.created)).all()  # FIFO
    if waiting_jobs:
        log.info('waiting jobs %s', waiting_jobs)

    for j in waiting_jobs:
        # find idle executor from given executors group
        best_executor = None
        idle_executors = idle_executors_by_group.get(j.executor_group_id, [])
        while best_executor is None:
            if len(idle_executors) == 0:
                break
            best_executor = idle_executors.pop()
            if best_executor.job:
                best_executor = None

        if best_executor is None:
            break

        # assign job to found executor
        best_executor.job = j
        j.executor_used = best_executor
        j.assigned = datetime.datetime.utcnow()
        db.session.commit()
        log.info("assigned job %s to executor %s", j, best_executor)

        counter += 1
        # if all idle executors used then stop assigning
        if counter == executors_count:
            break

    return counter


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('scheduler')

    # Create  Flask app instance
    app = Flask('Kraken Scheduler')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    return app


def main():
    app = create_app()

    with app.app_context():

        while True:
            t0 = time.time()
            jobs_cnt = assign_jobs_to_executors()
            t1 = time.time()

            dt = t1 - t0
            sleep_time = 5 - dt
            if sleep_time < 0:
                sleep_time = 0
            log.info("scheduled %d jobs in %.1fs, go sleep for %.1fs", jobs_cnt, dt, sleep_time)
            if sleep_time > 0:
                time.sleep(sleep_time)


if __name__ == "__main__":
    main()
