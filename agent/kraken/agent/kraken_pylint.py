import json
import logging
import subprocess

from . import utils
from . import tool

log = logging.getLogger(__name__)


def run_analysis(step, report_issue=None):
    log.info('run step')
    cwd = step.get('cwd', '.')
    rcfile = step['rcfile']
    modules_or_packages = step['modules_or_packages']
    cmd = 'pylint --exit-zero -f json --rcfile=%s %s' % (rcfile, modules_or_packages)
    ret, out = utils.execute(cmd, cwd=cwd)
    if ret != 0:
        log.error('pylint exited with non-zero retcode: %s', ret)
        return ret, 'pylint exited with non-zero retcode'

    result = json.loads(out)
    for issue in result:
        log.info('%s:%s  %s', issue['path'], issue['line'], issue['message'])
        report_issue(issue)

    return 0, ''


if __name__ == '__main__':
    tool.main()
