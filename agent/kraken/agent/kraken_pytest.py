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
import xml.etree.ElementTree as ET

from . import utils
from . import tool

log = logging.getLogger(__name__)


def collect_tests(step):
    params = step.get('params', '')
    cwd = step.get('cwd', '.')
    params = params.replace('-vv', '')
    params = params.replace('-v', '')
    cmd = 'PYTHONPATH=`pwd` pytest-3 --collect-only -q %s  | head -n -2' % params
    _, out = utils.execute(cmd, cwd=cwd, out_prefix='')
    tests = out
    tests = tests.splitlines()
    return tests


def run_tests(step, report_result=None):
    params = step.get('params', '')
    tests = step['tests']

    for test in tests:
        cwd = step.get('cwd', '.')
        params = [p for p in params.split() if p.startswith('-')]
        params = " ".join(params)
        cmd = 'PYTHONPATH=`pwd` pytest-3 -vv -r ap --junit-xml=result.xml %s %s' % (params, test)
        ret, _ = utils.execute(cmd, cwd=cwd, out_prefix='')

        result = dict(cmd=cmd, test=test)

        if ret != 0:
            result['status'] = 3  # error
            report_result(result)
            continue

        tree = ET.parse(os.path.join(cwd, 'result.xml'))
        root = tree.getroot()

        errors = 0
        if root.get('errors'):
            errors = int(root.get('errors'))

        failures = 0
        if root.get('failures'):
            failures = int(root.get('failures'))

        skips = 0
        if root.get('skips'):
            skips = int(root.get('skips'))

        if errors > 0:
            result['status'] = 3  # error
        elif failures > 0:
            result['status'] = 2  # failed
        elif skips > 0:
            result['status'] = 4  # disabled
        else:
            result['status'] = 1  # passed

        report_result(result)

    return 0, ''


if __name__ == '__main__':
    tool.main()
