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

import sys
import json
import socket
import inspect
import logging
import datetime
import argparse
import importlib
import traceback

from . import consts

log = logging.getLogger('tool')


class TestResultsCollector():
    def __init__(self, sock):
        self.sock = sock
        self.results = []
        self.last_reported = datetime.datetime.now()

    def report_result(self, result):
        self.results.append(result)

        now = datetime.datetime.now()
        # report results after 100 results or after 20 seconds
        if len(self.results) > 100 or (now - self.last_reported > datetime.timedelta(seconds=20)):
            self.flush()

    def flush(self):
        self.sock.send_json({'status': 'in-progress',
                             'test-results': self.results})
        self.results = []
        self.last_reported = datetime.datetime.now()


class IssuesCollector():
    def __init__(self, sock):
        self.sock = sock
        self.issues = []
        self.last_reported = datetime.datetime.now()

    def report_issue(self, issue):
        self.issues.append(issue)

        now = datetime.datetime.now()
        # report issues after 100 issues or after 20 seconds
        if len(self.issues) > 100 or (now - self.last_reported > datetime.timedelta(seconds=20)):
            self.flush()

    def flush(self):
        self.sock.send_json({'status': 'in-progress',
                             'issues': self.issues})
        self.issues = []
        self.last_reported = datetime.datetime.now()


class ArtifactsCollector():
    def __init__(self, sock):
        self.sock = sock
        self.artifacts = []
        self.last_reported = datetime.datetime.now()

    def report_artifact(self, artifact):
        self.artifacts.append(artifact)

        now = datetime.datetime.now()
        # report artifacts after 100 artifacts or after 20 seconds
        if len(self.artifacts) > 100 or (now - self.last_reported > datetime.timedelta(seconds=20)):
            self.flush()

    def flush(self):
        self.sock.send_json({'status': 'in-progress',
                             'artifacts': self.artifacts})
        self.artifacts = []
        self.last_reported = datetime.datetime.now()


def execute(sock, module, command, step_file_path):
    try:
        logging.basicConfig(format=consts.TOOL_LOG_FMT, level=logging.INFO)

        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)

        tool_name = step['tool']

        # log.info('started tool for step', tool=None)

        #tool = sys.modules['__main__']
        tool = importlib.import_module(module)

        log.info('run step tool %s, cmd %s', tool_name, command, tool=None)

        result = {'status': 'done'}
        ret = 0

        if command == 'get_commands':
            func_list = [o[0] for o in inspect.getmembers(
                tool) if inspect.isfunction(o[1]) and not o[0].startswith('_')]
            result['commands'] = func_list

        elif command == 'collect_tests':
            tests = tool.collect_tests(step)
            result['tests'] = tests

        elif command == 'run_tests':
            test_results_collector = TestResultsCollector(sock)
            report_result_cb = test_results_collector.report_result
            ret, msg = tool.run_tests(step, report_result=report_result_cb)
            test_results_collector.flush()

        elif command == 'run_analysis':
            issues_collector = IssuesCollector(sock)
            report_issue_cb = issues_collector.report_issue
            ret, msg = tool.run_analysis(step, report_issue=report_issue_cb)
            issues_collector.flush()

        elif command == 'run_artifacts':
            artifacts_collector = ArtifactsCollector(sock)
            report_artifact_cb = artifacts_collector.report_artifact
            ret, msg = tool.run_artifacts(step, report_artifact=report_artifact_cb)
            artifacts_collector.flush()

        elif command == 'run':
            ret, msg = tool.run(step)

        else:
            raise Exception('unknown command %s' % command)

        log.info('step tool %s, cmd %s done with retcode %s', tool_name, command, ret, tool=None)

        if ret != 0:
            if ret == 10000:
                result.update({'status': 'error', 'reason': 'step-timeout', 'msg': msg})
            else:
                result.update({'status': 'error', 'reason': 'retcode', 'retcode': ret, 'msg': msg})

        sock.send_json(result)
    except:
        log.exception('tool interrupted by exception', tool=None)
        exc = traceback.format_exc()
        sock.send_json({'status': 'error', 'reason': 'exception', 'msg': exc})


class JsonSocket(socket.socket):
    def __init__(self, address):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.connect((address[0], int(address[1])))
        except:
            log.error('problem with connecting to %s:%s', address[0], address[1])
            raise

    def send_json(self, data):
        data = json.dumps(data) + '\n'
        log.info('tool response: %s', data[:200], tool=None)
        self.sendall(bytes(data, "utf-8"))


class StdoutSock:
    def send_json(self, data):
        data = json.dumps(data) + '\n'
        log.info('tool response: %s', data[:200], tool=None)


def check_integrity():
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--return-address', help="TCP return address for reporting progress and end status.")
    parser.add_argument('-s', '--step-file', help="A path to step file.")
    parser.add_argument('-m', '--module', help="A full module name.")
    parser.add_argument('command', help="A command to execute")
    args = parser.parse_args()

    if args.command == 'check-integrity':
        if check_integrity():
            sys.exit(0)
        else:
            sys.exit(1)

    if args.return_address:
        with JsonSocket(args.return_address.split(':')) as sock:
            execute(sock, args.module, args.command, args.step_file)
    else:
        sock = StdoutSock()
        execute(sock, args.module, args.command, args.step_file)


if __name__ == '__main__':
    main()
