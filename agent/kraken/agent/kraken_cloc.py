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

import json
import logging

from . import utils
from . import tool

log = logging.getLogger(__name__)


def run_tests(step, report_result=None):
    cwd = step.get('cwd', '.')
    not_match_f = step.get('not-match-f', None)
    exclude_dir = step.get('exclude-dir', None)

    cmd = 'cloc . --json'
    if not_match_f:
        cmd += " --not-match-f '%s'" % not_match_f
    if exclude_dir:
        cmd += " --exclude-dir '%s'" % exclude_dir

    ret, out = utils.execute(cmd, cwd=cwd, out_prefix='')
    if ret != 0:
        log.error('cloc exited with non-zero retcode: %s', ret)
        return ret, 'cloc exited with non-zero retcode'

    data = json.loads(out)
    for f, v in data.items():
        if f == 'header':
            continue

        test = f
        values = dict(blank=dict(value=v['blank'], iterations=1),
                      comment=dict(value=v['comment'], iterations=1),
                      code=dict(value=v['code'], iterations=1),
                      total=dict(value=v['blank'] + v['comment'] + v['code'], iterations=1),
                      files=dict(value=v['nFiles'], iterations=1))
        result = dict(cmd='', status=1, test=test, values=values)
        report_result(result)

    return 0, ''


if __name__ == '__main__':
    tool.main()
