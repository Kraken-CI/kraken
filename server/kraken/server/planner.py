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
import logging
from urllib.parse import urlparse
from xmlrpc.server import SimpleXMLRPCServer

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from . import consts
from . import logs
from . import srvcheck
from . import models
from .. import version

log = logging.getLogger('planner')


class Planner:
    def __init__(self, db_url):
        job_defaults = dict(misfire_grace_time=180, coalesce=True, max_instances=1, next_run_time=None)
        self.scheduler = BackgroundScheduler(timezone='UTC', job_defaults=job_defaults)
        self.scheduler.add_jobstore('sqlalchemy', url=db_url + '?application_name=aps')
        self.scheduler.start()
        log.info('started planner scheduler')

        for idx, j in enumerate(self.get_jobs()):
            log.info('%d. name:%s trigger:%s func:%s args:%s kwargs:%s next:%s',
                     idx + 1, j['name'], j['trigger'], j['func'], j['args'], j['kwargs'], j['next_run_time'])

    def _job_to_dict(self, job):
        if isinstance(job.trigger, IntervalTrigger):
            trigger = 'interval'
        elif isinstance(job.trigger, DateTrigger):
            trigger = 'date'
        elif isinstance(job.trigger, CronTrigger):
            trigger = 'cron'
        else:
            trigger = 'unknown'
        next_run_time = ""
        if job.next_run_time:
            next_run_time = job.next_run_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        return dict(id=job.id, name=job.name, func=job.func_ref, args=job.args, kwargs=job.kwargs, trigger=trigger, next_run_time=next_run_time)

    def add_job(self, func=None, trigger=None, args=None, kwargs=None, job_id=None, name=None, misfire_grace_time=None,  # pylint: disable=too-many-arguments
                coalesce=True, max_instances=None, next_run_time=None, replace_existing=False, trigger_args=None):
        if trigger_args is None:
            trigger_args = {}

        all_kw_args = dict(args=args, kwargs=kwargs, id=job_id, name=name, replace_existing=replace_existing)

        if misfire_grace_time is not None:
            all_kw_args['misfire_grace_time'] = misfire_grace_time
        if coalesce is not None:
            all_kw_args['coalesce'] = coalesce
        if max_instances is not None:
            all_kw_args['max_instances'] = max_instances
        if next_run_time is not None:
            all_kw_args['next_run_time'] = next_run_time

        if trigger in ['interval', 'repo_interval']:
            trigger = IntervalTrigger(**trigger_args)
        elif trigger == 'date':
            trigger = DateTrigger(**trigger_args)
        elif trigger == 'cron':
            trigger = CronTrigger(**trigger_args)
        else:
            raise Exception('unknown trigger type %s' % trigger)

        all_kw_args['trigger'] = trigger
        log.info('add_job args: %s', all_kw_args)

        try:
            job = self.scheduler.add_job(func, **all_kw_args)
            log.info('add_job job:%s', job)
        except Exception:
            log.exception('some problem')
            raise
        return self._job_to_dict(job)

    def get_jobs(self):
        try:
            jobs = []
            for j in self.scheduler.get_jobs():
                jobs.append(self._job_to_dict(j))
        except Exception:
            log.exception('some problem')
            raise
        return jobs

    def reschedule_job(self, job_id=None, trigger=None, trigger_args=None):
        if trigger_args is None:
            trigger_args = {}

        log.info('reschedule_job args: %s %s %s', job_id, trigger, trigger_args)

        try:
            job = self.scheduler.reschedule_job(job_id, trigger=trigger, **trigger_args)
            log.info('reschedule_job job:%s', job)
        except Exception:
            log.exception('some problem')
            raise
        return self._job_to_dict(job)

    def remove_job(self, job_id=None):
        log.info('remove_job arg: %s', job_id)

        try:
            self.scheduler.remove_job(job_id)
            log.info('remove_job done')
        except Exception:
            log.exception('some problem')
            # raise


def _db_setup(db_url):
    # Create  Flask app instance
    app = Flask('Kraken Planner')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url + '?application_name=planner'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    models.db.init_app(app)

    # setup sentry
    with app.app_context():
        sentry_url = models.get_setting('monitoring', 'sentry_dsn')
        logs.setup_sentry(sentry_url)


def main():
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    # clickhouse_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', consts.DEFAULT_CLICKHOUSE_ADDR)

    srvcheck.check_postgresql(db_url)
    # srvcheck.check_tcp_service('clickhouse', clickhouse_addr, 9600)

    logs.setup_logging('planner')
    log.info('Kraken Planner started, version %s', version.version)

    # db setup
    _db_setup(db_url)

    # prepare planner and start it
    planner = Planner(db_url)

    o = urlparse(planner_url)
    planner_port = int(o.port)

    log.info('starting xml-rpc server for planner on port %d', planner_port)
    with SimpleXMLRPCServer(('0.0.0.0', planner_port), allow_none=True) as server:
        server.register_instance(planner)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")


if __name__ == '__main__':
    main()
