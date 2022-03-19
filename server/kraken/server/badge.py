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

import redis
from flask import abort, redirect

from . import consts
from . import utils


def get_branch_badge(branch_id, what=None):
    # get redis reference
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_KRAKEN_DB)

    try:
        int(branch_id)
    except Exception:
        abort(400, 'wrong branch id')

    if what is None:
        label = 'Kraken Build'
    elif what == 'tests':
        label = 'Kraken Tests'
    elif what == 'issues':
        label = 'Kraken Issues'

    # get data from redis
    # data in redis is prepared in bg/jobs.py, in _prepare_flow_summary()
    key = 'branch-%s' % branch_id
    data = rds.get(key)
    if not data:
        url = 'https://img.shields.io/badge/%s-%s-%s' % (label, 'no data', 'inactive')
        return redirect(url)

    data = json.loads(data)

    msg = '%s ' % data['label']

    if what is None:
        # flow status
        if data['errors']:
            color = 'critical'
            msg += 'failed'
        else:
            color = 'success'
            msg += 'success'

    elif what == 'tests':
        # flow tests
        if data['tests_total'] == 0:
            msg += 'no tests'
            color = 'informational'
        else:
            color = 'success'
            if data['tests_passed'] < data['tests_total']:
                color = 'important'
            pass_ratio = 100 * data['tests_passed'] / data['tests_total']
            msg += 'passed %.1f%%25 total %d' % (pass_ratio, data['tests_total'])
            if data['tests_regr'] > 0:
                msg += ' regressions %d' % data['tests_regr']
            if data['tests_fix'] > 0:
                msg += ' fixes %d' % data['tests_fix']

    elif what == 'issues':
        # flow issues
        color = 'success'
        if data['issues_total'] == 0:
            msg += 'no issues'
        else:
            msg += 'issues %d' % data['issues_total']
            color = 'important'
        if data['issues_new'] > 0:
            msg += 'new %d' % data['issues_new']
            color = 'critical'

    url = 'https://img.shields.io/badge/%s-%s-%s' % (label, msg, color)
    return redirect(url)
