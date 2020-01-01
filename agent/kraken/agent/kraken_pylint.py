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
        # prepare url for getting file
        git_url = out.strip()
        if '@' in git_url:
            git_url = git_url.split('@')[1]
        git_url = git_url.replace(':', '/')
        if git_url.endswith('.git'):
            git_url = git_url[:-4]

        # get remote branch
        branch = 'master'
        #cmd = 'git rev-parse --abbrev-ref --symbolic-full-name @{u}'
        cmd = 'git branch -a -r --contains HEAD'
        ret, out = utils.execute(cmd, cwd=cwd, tracing=False)
        if ret == 0:
            for l in out.splitlines():
                l = l.strip()
                if 'HEAD' in l:
                    continue
                branch = out.split('/')[1]
                break
    git_url = 'https://%s/blob/%s' % (git_url, branch)
    return git_url


def run_analysis(step, report_issue=None):
    cwd = step.get('cwd', '.')

    try:
        git_url = _get_git_url(cwd)
    except:
        git_url = None

    rcfile = step['rcfile']
    modules_or_packages = step['modules_or_packages']
    cmd = 'pylint --exit-zero -f json --rcfile=%s %s' % (rcfile, modules_or_packages)
    ret, out = utils.execute(cmd, cwd=cwd, out_prefix='')
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
