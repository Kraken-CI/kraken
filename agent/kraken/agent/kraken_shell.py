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

from . import utils


def run(step, **kwargs):  # pylint: disable=unused-argument
    cmd = step['cmd']
    cwd = step.get('cwd', None)

    # prepare env if needed
    extra_env = step.get('env', None)
    if extra_env:
        # take copy of current env otherwise new env would be nearly empty
        env = os.environ.copy()
        env.update(extra_env)
    else:
        env = None

    timeout = int(step.get('timeout', 60))
    ret, _ = utils.execute(cmd, cwd=cwd, env=env, timeout=timeout, out_prefix='')
    if ret != 0:
        return ret, 'cmd exited with non-zero retcode: %s' % ret
    return 0, ''
