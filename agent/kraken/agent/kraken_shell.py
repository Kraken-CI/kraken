# Copyright 2020-2023 The Kraken Authors
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
import platform


from . import utils
from . import sshkey


osname = platform.system()


def run(step, **kwargs):  # pylint: disable=unused-argument
    cmd = None
    script = step.get('script', None)
    if script is None:
        cmd = step['cmd']

    # prepare script if needed
    if script:
        if osname == 'Linux':
            suffix = '.sh'
        else:
            suffix = '.bat'

        fh = tempfile.NamedTemporaryFile(mode='w', prefix='kk-shell-', suffix=suffix, delete=False, encoding='utf-8')

        if osname == 'Linux':
            fh.write('set -ex\n')
        fh.write(script)
        fname = fh.name
        fh.close()

        if osname == 'Linux':
            shell_exe = step.get('shell_exe', '/bin/bash')
        elif osname == 'Windows':
            shell_exe = step.get('shell_exe', None)
        else:
            raise Exception('not implemented')

        if shell_exe:
            cmd = '%s %s' % (shell_exe, fname)
        else:
            cmd = fname
        shell_exe = None
    else:
        if osname == 'Linux':
            shell_exe = step.get('shell_exe', '/bin/sh')
        elif osname == 'Windows':
            shell_exe = step.get('shell_exe', None)
        else:
            raise Exception('not implemented')

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

    # start ssh-agent if needed
    if 'ssh-key' in step:
        # username = step['ssh-key']['username']
        # url = '%s@%s' % (username, url)
        key = step['ssh-key']['key']
        ssh_agent = sshkey.SshAgent()
        ssh_agent.add_key(key)
    else:
        ssh_agent = None

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
        if ssh_agent is not None:
            ssh_agent.shutdown()

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
