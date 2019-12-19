import subprocess
import logging

from . import utils
from . import tool

log = logging.getLogger(__name__)


def run(step, **kwargs):
    log.info('run step')
    url = step['checkout']
    dest = ''
    if 'destination' in step:
        dest = step['destination']
    ret, out = utils.execute('git clone %s %s' % (url, dest))
    if ret != 0:
        return ret, 'git clone exited with non-zero retcode'

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
