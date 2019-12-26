import json
import logging
import subprocess

from . import utils
from . import tool

log = logging.getLogger(__name__)


def _get_git_url(cwd):
    cmd = "git config --get remote.origin.url"
    ret, out = utils.execute(cmd, cwd=cwd, tracing=False)
    if ret == 0:
        git_url = out.strip()
        if '@' in git_url:
            git_url = git_url.split('@')[1]
        git_url = git_url.replace(':', '/')
        if git_url.endswith('.git'):
            git_url = git_url[:-4]

        # get remote branch
        branch = 'master'
        cmd = 'git rev-parse --abbrev-ref --symbolic-full-name @{u}'
        ret, out = utils.execute(cmd, cwd=cwd)
        if ret == 0:
            branch = out.split('/')[1]
    git_url = 'https://%s/blob/%s' % (git_url, branch)
    return git_url


def run_analysis(step, report_issue=None):
    log.info('run step')
    cwd = step.get('cwd', '.')

    try:
        git_url = _get_git_url(cwd)
    except:
        log.info('getting git url failed')
        git_url = None

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
        if git_url:
            issue['url'] = '%s/%s#L%s' % (git_url, issue['path'], issue['line'])
        report_issue(issue)

    return 0, ''


if __name__ == '__main__':
    tool.main()
