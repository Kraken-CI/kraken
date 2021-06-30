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
from . import consts
from . import kkrq

log = logging.getLogger(__name__)


def trigger_run(stage_id, flow_kind=consts.FLOW_KIND_CI, reason=None):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    args = (stage_id, flow_kind, reason)

    log.info('trigger run for stage %s', stage_id)
    kkrq.enq_neck(bg_jobs.trigger_run, *args, ignore_args=[2])


def refresh_schema_repo(stage_id):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    log.info('refresh stage %s schema from repo', stage_id)
    kkrq.enq_neck(bg_jobs.refresh_schema_repo, stage_id, None, ignore_args=[1])
