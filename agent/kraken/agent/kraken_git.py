import subprocess
import logging

import utils
import tool

log = logging.getLogger(__name__)


def run(step, **kwargs):
    log.info('run step')
    url = step['checkout']
    ret, out = utils.execute('git clone %s' % url)
    if ret != 0:
        return ret, 'git clone exited with non-zero retcode'
    return 0, ''


if __name__ == '__main__':
    tool.main()
