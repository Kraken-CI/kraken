import os
import sys
import json
import socket
import pkgutil
import inspect
import logging
import datetime
import argparse
import traceback

LOG_FMT = '%(asctime)s %(levelname)-4.4s p:%(process)5d %(module)8.8s:%(lineno)-5d %(message)s'

log = logging.getLogger(__name__)


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


def execute(sock, command, step_file_path):
    try:
        logging.basicConfig(format=LOG_FMT, level=logging.INFO)
        log.info('started tool for step')

        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)

        tool_name = step['tool']
        #base_dir = os.path.dirname(os.path.abspath(__file__))
        #sys.path.append(base_dir)
        tool = sys.modules['__main__']

        log.info('run step tool %s, cmd %s', tool_name, command)

        result = {'status': 'done'}
        ret = 0

        if command == 'get_commands':
            func_list = [o[0] for o in inspect.getmembers(tool) if inspect.isfunction(o[1]) and not o[0].startswith('_')]
            result['commands'] = func_list

        elif command == 'collect_tests':
            tests = tool.collect_tests(step)
            result['tests'] = tests

        elif command == 'run_tests':
            test_results_collector = TestResultsCollector(sock)
            report_result_cb = test_results_collector.report_result
            ret, msg = tool.run_tests(step, report_result=report_result_cb)
            test_results_collector.flush()

        elif command == 'run':
            ret, msg = tool.run(step)

        else:
            raise Exception('unknown command %s' % command)

        log.info('step tool %s, cmd %s done with retcode %s', tool_name, command, ret)

        if ret != 0:
            result.update({'status': 'error', 'reason': 'retcode', 'retcode': ret, 'msg': msg})

        sock.send_json(result)
    except:
        log.exception('tool interrupted by exception')
        exc = traceback.format_exc()
        sock.send_json({'status': 'error', 'reason': 'exception', 'msg': exc})


class JsonSocket(socket.socket):
    def __init__(self, address):
        socket.socket.__init__(self, socket.AF_INET, socket.SOCK_STREAM)
        self.connect((address[0], int(address[1])))

    def send_json(self, data):
        data = json.dumps(data) + '\n'
        log.info('tool response: %s', data[:200])
        self.sendall(bytes(data, "utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--return-address', help="TCP return address for reporting progress and end status.")
    parser.add_argument('-s', '--step-file', help="A path to step file.")
    parser.add_argument('command', help="A command to execute")
    args = parser.parse_args()

    with JsonSocket(args.return_address.split(':')) as sock:
        execute(sock, args.command, args.step_file)
