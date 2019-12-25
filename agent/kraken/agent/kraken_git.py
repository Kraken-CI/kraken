import subprocess
import logging

from . import utils
from . import tool
from . import sshkey

log = logging.getLogger(__name__)


def run(step, **kwargs):
    log.info('run step')
    url = step['checkout']
    dest = ''
    if 'destination' in step:
        dest = step['destination']

    ssh_agent = None
    if 'ssh-key' in step:
        username = step['ssh-key']['username']
        #url = '%s@%s' % (username, url)
        key = step['ssh-key']['key']
        ssh_agent = sshkey.SshAgent()
        ssh_agent.add_key(key)
    elif 'access-token' in step:
        access_token = step['access-token']
        url = 'https://%s@%s' % (access_token, url.replace(':', '/'))

    try:
        ret, out = utils.execute('git clone %s %s' % (url, dest), mask=access_token)
        if ret != 0:
            return ret, 'git clone exited with non-zero retcode'
    finally:
        if ssh_agent is not None:
            ssh_agent.shutdown()

    if 'trigger_data' in step:
        if url.endswith('.git'):
            url = url[:-4]
        url = url.replace(':', '/')
        if url.endswith(step['trigger_data']['repo']):
            commit = step['trigger_data']['after']
            if dest:
                cwd = dest
            else:
                cwd = url.split('/')[-1]
            ret, out = utils.execute('git checkout %s' % commit, cwd=cwd)
            if ret != 0:
                return ret, 'git checkout exited with non-zero retcode'

    return 0, ''


if __name__ == '__main__':
    tool.main()
