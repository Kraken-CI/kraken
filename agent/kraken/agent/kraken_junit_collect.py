# Copyright 2021 The Kraken Authors
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
import glob
import logging
import xml.etree.ElementTree as ET


log = logging.getLogger(__name__)


def _parse_junit_file(fp, report_result):
    log.info('parsing %s', fp)

    tree = ET.parse(fp)
    root = tree.getroot()

    passed = 0
    failed = 0
    error = 0
    disabled = 0
    for tc in root.iter('testcase'):
        test = '%s::%s' % (tc.get('classname'), tc.get('name'))

        if tc.find('error') is not None:
            status = 3  # error
            status_txt = 'error'
            error += 1
        elif tc.find('failure') is not None:
            status = 2  # failed
            status_txt = 'failed'
            failed += 1
        elif tc.find('skipped') is not None:
            status = 4  # disabled
            status_txt = 'disabled'
            disabled += 1
        else:
            status = 1  # passed
            status_txt = 'passed'
            passed += 1

        if report_result:
            res = dict(cmd='', test=test, status=status)
            report_result(res)
        else:
            log.info('  %s --- %s', test, status_txt)

    log.info('  passed=%d, failed=%d, disabled=%d, error=%d',
             passed, failed, disabled, error)

    return passed, failed, disabled, error


def run_tests(step, report_result=None):
    cwd = step.get('cwd', '.')
    file_glob = step.get('file_glob', '**/*.xml')
    file_glob = os.path.join(cwd, file_glob)

    passed = failed = disabled = error = 0

    for fp in glob.iglob(file_glob, recursive=True):
        counts = _parse_junit_file(fp, report_result)
        passed += counts[0]
        failed += counts[1]
        disabled += counts[2]
        error += counts[3]

    log.info('TOTAL:  passed=%d, failed=%d, disabled=%d, error=%d',
             passed, failed, disabled, error)

    return 0, ''


def main():
    logging.basicConfig(level=logging.INFO)
    # step = dict(cwd='/tmp/lucene',
    #             file_glob='**/test-results/test/*.xml')
    step = dict(cwd='/home/godfryd/repos/kraken/agent/kraken/agent',
                file_glob='ju-rf.xml')

    run_tests(step)


if __name__ == '__main__':
    main()
