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

import logging

from .bg import jobs as bg_jobs
from .bg.clry import app as clryapp
from . import consts

log = logging.getLogger(__name__)

import base64
import json


def _is_in_celery_queue(func, args):
    with clryapp.pool.acquire(block=True) as conn:
        tasks = conn.default_channel.client.lrange('celery', 0, -1)

    args = repr(args)

    for task in tasks:
        j = json.loads(task)
        hdrs = j['headers']
        f = hdrs['task']
        a = hdrs['argsrepr']
        if f == func and a == args:
            return True

    return False


def trigger_run(stage_id, flow_kind=consts.FLOW_KIND_CI):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    args = (stage_id, flow_kind)

    if _is_in_celery_queue('kraken.server.bg.jobs.trigger_run', args):
        log.info('skipped trigger run for stage %s as it is already in celery queue', stage_id)
        return

    log.info('trigger run for stage %s', stage_id)
    t = bg_jobs.trigger_run.delay(*args)
    log.info('triggering run for stage %s, bg processing: %s', stage_id, t)


def refresh_schema_repo(stage_id):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    args = (stage_id,)

    if _is_in_celery_queue('kraken.server.bg.jobs.refresh_schema_repo', args):
        log.info('skipped refresh stage %s schema from repo as it is already in celery queue', stage_id)
        return

    log.info('refresh stage %s schema from repo', stage_id)
    t = bg_jobs.refresh_schema_repo.delay(stage_id)
    log.info('refreshing stage %s schema from repo, bg processing: %s', stage_id, t)
