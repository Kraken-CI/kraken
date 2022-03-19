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
import time
import json
import logging

import redis

from . import logs
from . import consts
from . import srvcheck
from . import utils
from .. import version
from .bg import jobs as bg_jobs
from . import kkrq

log = logging.getLogger('qneck')


def _check_jobs(waiting_jobs, executing_jobs):
    # check of jobs then were sent for execution
    # if they are maybe completed
    completed = []
    for key, job in executing_jobs.items():
        status = job.get_status()
        if status in ['finished', 'failed']:
            # TODO: what about failed retries?
            completed.append(key)

    # go through completed jobs and 1) remove them
    # from execution jobs and 2) if there is the same
    # job in waiting jobs then run it
    for key in completed:
        del executing_jobs[key]

        vals = waiting_jobs.get(key, None)
        if vals is None:
            continue

        func, args = vals
        job = kkrq.enq(func, *args)
        executing_jobs[key] = job

        del waiting_jobs[key]


def _main_loop():
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    srvcheck.wait_for_service('redis', redis_addr, 6379)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_RQ_DB)

    ps = rds.pubsub()
    ps.subscribe('qneck')

    waiting_jobs = {}
    executing_jobs = {}

    last_check = time.time()

    while True:
        try:
            # get the job from redis pubsub channel
            # wait for it up to 1 second, if there is
            # nothing then None is returned
            msg = ps.get_message(timeout=1)

            # if received not interesting message
            # then check what is happening with jobs
            if not msg or msg['type'] != 'message':
                if time.time() - last_check > 5:
                    _check_jobs(waiting_jobs, executing_jobs)
                    last_check = time.time()
                continue

            log.info('qneck: received msg: %s', msg)

            # unpack message
            data = json.loads(msg['data'])
            func_name = data['func']
            args = tuple(data['args'])
            ignore_args = data['ignore_args']
            func = getattr(bg_jobs, func_name)

            if ignore_args:
                key = [func]
                for idx, a in enumerate(args):
                    if idx in ignore_args:
                        continue
                    key.append(a)
                key = tuple(key)
            else:
                key = (func, *args)

            # if the same jobs as received one is waiting
            # then drop this one - we keep only one waiting job
            if key in waiting_jobs:
                log.info('qneck: skipped %s%s as it is already in queue', func, args)
                continue

            # if the same job as received one is being executed
            # then put it in waiting jobs - it will be executed
            # current one is finished
            if key in executing_jobs:
                waiting_jobs[key] = (func, args)
                log.info('qneck: queued %s%s as it is already being executed', func, args)
                continue

            # if the same job as received job is not waiting
            # nor it is being executed then run the received job
            job = kkrq.enq(func, *args)
            executing_jobs[key] = job

        except Exception:
            log.exception('IGNORED EXCEPTION')
            time.sleep(1)


def main():
    logs.setup_logging('rq')
    log.info('Kraken QNeck started, version %s', version.version)

    try:
        _main_loop()
    except Exception:
        log.exception('IGNORED EXCEPTION')
        time.sleep(10)


if __name__ == "__main__":
    main()
