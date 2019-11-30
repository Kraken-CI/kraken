import os
import sys
import datetime
import logging

import .bg import jobs as bg_jobs
from . import consts

log = logging.getLogger(__name__)


def trigger_run(stage_id):
    logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    log.info('trigger run for stage %s' % stage_id)

    t = bg_jobs.trigger_run.delay(stage_id)
    log.info('triggering run for stage %s, bg processing: %s', stage_id, t)
