# Copyright 2023 The Kraken Authors
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

from . import utils
from . import tool

log = logging.getLogger(__name__)


def run_data(step, report_data=None):
    cwd = step.get('cwd', '.')
    fpath = step.get('file', None)
    value = step.get('value', None)

    if value:
        report_data('')
        return 0, ''

    if not fpath:
        msg = 'missing file path in step definition'
        log.error(msg)
        return 1, msg

    fpath = os.path.join(cwd, fpath)

    if not os.path.exists(fpath):
        msg = 'missing file path at %s' % fpath
        log.error(msg)
        return 1, msg

    try:
        with open(fpath) as fp:
            data = fp.read()
    except Exception as e:
        log.exception('problem with reading file %s', fpath)
        msg = 'problem with reading file %s: %s' % (fpath, str(e))
        return 1, msg

    report_data(data)

    return 0, ''


if __name__ == '__main__':
    tool.main()
