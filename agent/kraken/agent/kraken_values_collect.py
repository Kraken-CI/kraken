# Copyright 2022 The Kraken Authors
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

from . import tool
from . import consts

log = logging.getLogger(__name__)



def run_tests(step, report_result=None):
    cwd = step.get('cwd', '.')
    files = step['files']

    for f in files:
        fname = f['name']
        ns = f.get('namespace', None)

        if ns:
            test = ns
        else:
            test = fname

        result = dict(test=test, cmd='', status=consts.TC_RESULT_PASSED)
        result['values'] = {}

        fpath = os.path.join(cwd, fname)

        if not os.path.exists(fpath):
            result['status'] = consts.TC_RESULT_ERROR
            result['msg'] = 'missing %s file' % fpath
            report_result(result)
            continue

        with open(fpath) as fh:
            try:
                data = json.load(fh)
            except Exception:
                result['status'] = consts.TC_RESULT_ERROR
                result['msg'] = 'cannot parse %s file' % fpath
                report_result(result)
                continue

        for name, val in data.items():
            result['values'][name] = {'value': val}

        log.info('result %s', result)
        report_result(result)

    return 0, ''


if __name__ == '__main__':
    tool.main()
