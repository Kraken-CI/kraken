#!/usr/bin/env python3

# Copyright 2021 The Kraken Authors
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
import json
import logging

import rq
import redis
from flask import Flask

from . import srvcheck
from . import consts
from . import logs
from . import utils
from .. import version
from .models import db, get_setting

log = logging.getLogger('rq')


def enq(func, *args, **kwargs):
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_RQ_DB)
    q = rq.Queue('kq', connection=rds)
    # job timeout is 20mins (1200s), interval between retries is 60s
    j = q.enqueue(func, args=args, kwargs=kwargs, retry=rq.Retry(max=2, interval=5), job_timeout=1200)
    log.info('put to bg processing: %s', j)
    return j


def enq_neck(func, *args, ignore_args=None):
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_RQ_DB)
    data = dict(func=func.__name__,
                args=args,
                ignore_args=ignore_args)
    data = json.dumps(data)
    rds.publish('qneck', data)
    log.info('enqueued func %s with args: %s and %s', func.__name__, args, ignore_args)


def get_jobs():
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_RQ_DB)
    q = rq.Queue('kq', connection=rds)

    jobs_ids = q.scheduled_job_registry.get_job_ids()
    scheduled_jobs = rq.job.Job.fetch_many(jobs_ids, connection=rds)

    jobs_ids = q.started_job_registry.get_job_ids()
    started_jobs = rq.job.Job.fetch_many(jobs_ids, connection=rds)

    jobs_ids = q.finished_job_registry.get_job_ids()
    finished_jobs = rq.job.Job.fetch_many(jobs_ids, connection=rds)

    jobs_ids = q.failed_job_registry.get_job_ids()
    failed_jobs = rq.job.Job.fetch_many(jobs_ids, connection=rds)

    jobs_ids = q.deferred_job_registry.get_job_ids()
    deferred_jobs = rq.job.Job.fetch_many(jobs_ids, connection=rds)

    return scheduled_jobs, started_jobs, finished_jobs, failed_jobs, deferred_jobs


# TODO: it does not work because rq always traces the exception
def _exception_handler(job, exc_type, exc_value, traceback):  # pylint: disable=unused-argument
    ignore_excs = ['ix_agents_address']
    for ex in ignore_excs:
        if ex in str(exc_value) or ex in str(traceback):
            return
    log.exception('IGNORED')


def main():
    # check deps
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    srvcheck.wait_for_service('planner', planner_url, 7997)

    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    srvcheck.wait_for_service('redis', redis_addr, 6379)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_RQ_DB)

    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    srvcheck.check_postgresql(db_url)

    logs.setup_logging('rq')
    log.info('Kraken RQ started, version %s', version.version)

    # Create Flask app instance
    app = Flask('Kraken RQ')
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url + '?application_name=rq'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    # setup sentry
    with app.app_context():
        sentry_url = get_setting('monitoring', 'sentry_dsn')
        logs.setup_sentry(sentry_url)

    worker = rq.Worker('kq', connection=rds, exception_handlers=[_exception_handler])
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
