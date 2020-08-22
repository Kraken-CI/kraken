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

log = logging.getLogger(__name__)


def trigger_run(stage_id):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    log.info('trigger run for stage %s', stage_id)

    t = bg_jobs.trigger_run.delay(stage_id)
    log.info('triggering run for stage %s, bg processing: %s', stage_id, t)
