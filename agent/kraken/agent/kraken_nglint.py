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

import os
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
    except Exception:
        git_url = None

    repo_parent = None
    cmd = 'git rev-parse --show-toplevel'
    ret, out = utils.execute(cmd, cwd=cwd, tracing=False)
    if ret == 0:
        repo_parent = out.strip() + os.path.sep
    if not repo_parent:
        repo_parent = os.path.abspath(cwd) + os.path.sep

    cmd = 'npx ng lint --format json --force --silent'
    ret, out = utils.execute(cmd, cwd=cwd, out_prefix='', timeout=180)
    if ret != 0:
        log.error('ng lint exited with non-zero retcode: %s: %s', ret, out)
        return ret, 'ng lint exited with non-zero retcode'


    result = json.loads(out)
    for file_issues in result:
        if repo_parent:
            filepath = file_issues['filePath'].replace(repo_parent, '')
        else:
            filepath = file_issues['filePath']

        for issue in file_issues['messages']:
            log.info('%s:%s  %s', filepath, issue['startPosition']['line'], issue['failure'])
            if issue['severity'] == 2:
                severity = 'error'
            elif issue['severity'] == 1:
                severity = 'warning'
            else:
                severity = 'other'
            line = issue['line']
            issue2 = dict(path=filepath,
                          line=line,
                          column=issue['column'],
                          message=issue['message'],
                          symbol=issue['messageId'],
                          type=severity)
            if git_url:
                issue2['url'] = '%s/%s#L%s' % (git_url, filepath, line)
            report_issue(issue2)

    return 0, ''


if __name__ == '__main__':
    tool.main()
