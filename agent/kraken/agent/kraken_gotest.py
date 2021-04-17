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

import json
import queue
import logging
import threading
from functools import partial

from . import utils


log = logging.getLogger(__name__)


def _process_output(q, text):
    for l in text.splitlines():
        try:
            data = json.loads(l)
        except:
            log.error('failed parsing: %s', l)
            log.exception('IGNORED EXCEPTION')
            continue

        if 'Output' in data:
            log.info(data['Output'].rstrip())

        if 'Action' not in data:
            continue

        if data['Action'] in ['pass', 'skip', 'fail']:
            result = data['Action']
            if 'Test' not in data:
                continue
            test = data['Test']
            if 'Package' in data:
                test = '%s::%s' % (data['Package'], test)

            q.put((test, result))


def _upload_results(q, finished, report_result):
    while not finished.is_set():
        try:
            item = q.get(timeout=0.1)
        except queue.Empty:
            finished.wait(0.1)
            continue
        test, result = item
        if report_result:
            if result == 'pass':
                status = 1  # passed
            elif result == 'fail':
                status = 2  # failed
            elif result == 'skip':
                status = 4  # disabled
            else:
                status = 3  # error
            res = dict(cmd='', test=test, status=status)
            report_result(res)
        else:
            log.info('%s --- %s', test, result)
        q.task_done()


def run_tests(step, report_result=None):
    cwd = step.get('cwd', None)
    go_exe = step.get('go_exe', 'go')
    params = step.get('params', '')
    timeout = int(step.get('timeout', 60))

    cmd = '%s test -json %s' % (go_exe, params)

    q = queue.Queue()
    finished = threading.Event()
    uploader = threading.Thread(target=_upload_results, args=(q, finished, report_result))
    uploader.start()

    _process_output2 = partial(_process_output, q)

    ret = utils.execute(cmd, cwd=cwd, output_handler=_process_output2, tracing=False, timeout=timeout)

    q.join()
    finished.set()
    uploader.join()

    if ret != 0:
        log.error('go test exited with non-zero retcode: %s', ret)
        return ret, 'go test exited with non-zero retcode'

    return 0, ''


def main():
    logging.basicConfig(level=logging.INFO)
    step = dict(cwd='/tmp/hgo/hugo',
                go_exe='/usr/bin/go',
                params='-p 1 ./...')
    run_tests(step)


if __name__ == '__main__':
    main()
