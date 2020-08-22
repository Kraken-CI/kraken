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

from . import utils
from . import tool
from . import sshkey

log = logging.getLogger(__name__)


def run(step, **kwargs):  # pylint: disable=unused-argument
    url = step['checkout']
    dest = ''
    if 'destination' in step:
        dest = step['destination']

    ssh_agent = None
    access_token = None
    if 'ssh-key' in step:
        # username = step['ssh-key']['username']
        # url = '%s@%s' % (username, url)
        key = step['ssh-key']['key']
        ssh_agent = sshkey.SshAgent()
        ssh_agent.add_key(key)
    elif 'access-token' in step:
        access_token = step['access-token']
        if url.startswith('git@'):
            url = url[4:]
        url = 'https://%s@%s' % (access_token, url.replace(':', '/'))

    try:
        ret, _ = utils.execute('git clone %s %s' % (url, dest), mask=access_token, out_prefix='')
        if ret != 0:
            return ret, 'git clone exited with non-zero retcode'
    finally:
        if ssh_agent is not None:
            ssh_agent.shutdown()

    if 'trigger_data' in step:
        if step['trigger_data']['repo'] == step['http_url']:
            commit = step['trigger_data']['after']
            if dest:
                cwd = dest
            else:
                cwd = url.split('/')[-1]
                if cwd.endswith('.git'):
                    cwd = cwd[:-4]
            ret, _ = utils.execute('git checkout %s' % commit, cwd=cwd, out_prefix='')
            if ret != 0:
                return ret, 'git checkout exited with non-zero retcode'

    return 0, ''


if __name__ == '__main__':
    tool.main()
