# Copyright 2020-2022 The Kraken Authors
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
import tempfile

from . import utils


def run(step, **kwargs):  # pylint: disable=unused-argument
    cmd = None
    script = step.get('script', None)
    if script is None:
        cmd = step['cmd']

    # prepare script if needed
    if script:
        fh = tempfile.NamedTemporaryFile(mode='w', prefix='kk-shell-', suffix='.sh', delete=False)
        fh.write('set -e\n')
        fh.write(script)
        fname = fh.name
        fh.close()

        shell_exe = step.get('shell_exe', '/bin/bash')
        cmd = '%s %s' % (shell_exe, fname)
        shell_exe = None
    else:
        shell_exe = step.get('shell_exe', '/bin/sh')

    # prepare env if needed
    extra_env = step.get('env', None)
    if extra_env:
        # take copy of current env otherwise new env would be nearly empty
        env = os.environ.copy()
        env.update(extra_env)
    else:
        env = None

    cwd = step.get('cwd', None)
    timeout = int(step.get('timeout', 60))

    # testing
    ignore_output = True
    if 'testing' in kwargs and kwargs['testing']:
        ignore_output = False

    # execute
    try:
        resp = utils.execute(cmd, cwd=cwd, env=env, timeout=timeout, out_prefix='', ignore_output=ignore_output,
                             executable=shell_exe)
    except Exception as ex:
        return 1, str(ex)
    finally:
        if script:
            os.unlink(fname)

    if 'testing' in kwargs and kwargs['testing']:
        ret, out = resp
    else:
        ret = resp

    if ret != 0:
        result = [ret, 'cmd exited with non-zero retcode: %s' % ret]
    else:
        result = [0, '']

    if 'testing' in kwargs and kwargs['testing']:
        result.append(out)

    return result
