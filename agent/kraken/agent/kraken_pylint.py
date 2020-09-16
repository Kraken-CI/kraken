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

import json
import logging

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
                branch = l.split('/')[1]
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
    pylint_exe = step.get('pylint_exe', 'pylint')
    cmd = '%s --exit-zero -f json --rcfile=%s %s' % (pylint_exe, rcfile, modules_or_packages)
    ret, out = utils.execute(cmd, cwd=cwd, out_prefix='', timeout=180)
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
