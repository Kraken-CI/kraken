#!/usr/bin/env python3

import os
import logging

from xmlrpc.server import SimpleXMLRPCServer
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from . import consts
from . import logs

log = logging.getLogger('planner')


class Planner:
    def __init__(self):
        job_defaults = dict(misfire_grace_time=180, coalesce=True, max_instances=1, next_run_time=None)
        self.scheduler = BackgroundScheduler(timezone='UTC', job_defaults=job_defaults)
        db_url = os.environ.get('DB_URL', "postgresql://kraken:kk123@localhost:5433/kraken")
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

    def add_job(self, func=None, trigger=None, args=None, kwargs=None, job_id=None, name=None, misfire_grace_time=None,
                coalesce=None, max_instances=None, next_run_time=None, replace_existing=False, trigger_args={}):
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

    def reschedule_job(self, job_id=None, trigger=None, trigger_args={}):
        log.info('reschedule_job args: %s %s %s', job_id, trigger, trigger_args)

        try:
            job = self.scheduler.reschedule_job(job_id, trigger=trigger, **trigger_args)
            log.info('reschedule_job job:%s', job)
        except:
            log.exception('some problem')
            raise
        return self._job_to_dict(job)

    def remove_job(self, job_id=None):
        log.info('remove_job arg: %s %s %s', job_id)

        try:
            self.scheduler.remove_job(job_id)
            log.info('remove_job done')
        except:
            log.exception('some problem')
            #raise


def main():
    logs.setup_logging('planner')

    host = os.environ.get('PLANNER_HOST', 'localhost')
    port = os.environ.get('PLANNER_PORT', 8000)

    planner = Planner()

    log.info('starting xml-rpc server for planner')
    with SimpleXMLRPCServer((host, port), allow_none=True) as server:
        server.register_instance(planner)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")


if __name__ == '__main__':
    main()
