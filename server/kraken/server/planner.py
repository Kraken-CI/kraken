#!/usr/bin/env python3

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

log = logging.getLogger('planner')


class Planner:
    def __init__(self, db_url):
        job_defaults = dict(misfire_grace_time=180, coalesce=True, max_instances=1, next_run_time=None)
        self.scheduler = BackgroundScheduler(timezone='UTC', job_defaults=job_defaults)
        self.scheduler.add_jobstore('sqlalchemy', url=db_url)
        self.scheduler.start()
        log.info('started planner scheduler')

    def _job_to_dict(self, job):
        #log.info('trigger %s', dir(j.trigger))
        if isinstance(job.trigger, IntervalTrigger):
            trigger = 'interval'
        elif isinstance(job.trigger, DateTrigger):
            trigger = 'date'
        elif isinstance(job.trigger, CronTrigger):
            trigger = 'cron'
        else:
            trigger = 'unknown'
        return dict(id=job.id, name=job.name, func=job.func_ref, args=job.args, kwargs=job.kwargs, trigger=trigger)

    def add_job(self, func=None, trigger=None, args=None, kwargs=None, job_id=None, name=None, misfire_grace_time=None,  # pylint: disable=too-many-arguments
                coalesce=None, max_instances=None, next_run_time=None, replace_existing=False, trigger_args=None):
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

        if trigger == 'interval':
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
        except:
            log.exception('some problem')
            raise
        return self._job_to_dict(job)

    def get_jobs(self):
        log.info('get_jobs')

        try:
            jobs = []
            for j in self.scheduler.get_jobs():
                jobs.append(self._job_to_dict(j))
            log.info('get_jobs jobs:%s', jobs)
        except:
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
        except:
            log.exception('some problem')
            raise
        return self._job_to_dict(job)

    def remove_job(self, job_id=None):
        log.info('remove_job arg: %s', job_id)

        try:
            self.scheduler.remove_job(job_id)
            log.info('remove_job done')
        except:
            log.exception('some problem')
            # raise


def _db_setup(db_url):
    # Create  Flask app instance
    app = Flask('Kraken Planner')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    models.db.init_app(app)
    models.db.create_all(app=app)
    with app.app_context():
        models.prepare_initial_data()


def main():
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    logstash_addr = os.environ.get('KRAKEN_LOGSTASH_ADDR', consts.DEFAULT_LOGSTASH_ADDR)

    srvcheck.check_postgresql(db_url)
    #srvcheck.check_tcp_service('logstash', logstash_addr, 9600)

    logs.setup_logging('planner')
    log.info('Kraken Planner started')

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
