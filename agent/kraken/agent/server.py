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
import time
import socket
import logging
import datetime
import urllib.request
from urllib.parse import urljoin, urlparse

from . import config
from . import sysutils
from . import consts

log = logging.getLogger(__name__)


def _send_http_request(url, data):
    url = urljoin(url, 'backend')
    data = json.dumps(data)
    data = data.encode('utf-8')
    req = urllib.request.Request(url=url, data=data, headers={'content-type': 'application/json'})
    resp = None

    # Codes description:
    #     -2 - 'Name or service not known'
    #     32 - 'Broken pipe'
    #     100 - 'Network is down'
    #     101 - 'Network is unreachable'
    #     110 - 'Connection timed out'
    #     111 - 'Connection refused'
    #     112 - 'Host is down'
    #     113 - 'No route to host'
    #     10053 - 'An established connection was aborted by the software in your host machine'
    #     10054 - An existing connection was forcibly closed by the remote host
    #     10060 - 'Connection timed out'
    #     10061 - 'No connection could be made because the target machine actively refused it'
    connection_errors = [-2, 32, 100, 101, 110, 111, 112, 113, 10053, 10054, 10060, 10061]

    while resp is None:
        try:
            with urllib.request.urlopen(req, timeout=120) as f:
                resp = f.read().decode('utf-8')
        # except socket.error as e:
        #     if e.errno in connection_errors:
        #         # TODO: just warn and sleep for a moment
        except urllib.error.URLError as e:
            # pylint: disable=no-member
            if e.__context__ and e.__context__.errno in connection_errors:
                log.warning('url connection problem to %s: %s, trying one more time in 5s', url, str(e))
                time.sleep(5)
            else:
                raise
        except ConnectionError as e:
            log.warning('connection problem to %s: %s, trying one more time in 5s', url, str(e))
            time.sleep(5)
        except socket.timeout:
            log.warning('connection timeout to %s, trying one more time in 5s', url)
            time.sleep(5)
        except Exception:
            log.exception('some problem with connecting to server to %s', url)
            log.info('trying one more time in 5s')
            time.sleep(5)

    resp = json.loads(resp)
    return resp


class Server():
    def __init__(self):
        self.srv_addr = config.get('server')
        self.checks_num = 0
        self.last_check = datetime.datetime.now()
        slot = os.environ.get('KRAKEN_AGENT_SLOT', None)  # this is used in the case when agent is run in Docker Swarm
        builtin = os.environ.get('KRAKEN_AGENT_BUILTIN', None)
        if slot is not None:
            self.my_addr = 'agent.%s' % slot
        elif builtin is not None:
            self.my_addr = 'agent'
        else:
            srv_ip_addr = urlparse(self.srv_addr).hostname
            self.my_addr = sysutils.get_my_ip(srv_ip_addr)

    def check_server(self):
        current_addr = self.srv_addr
        self.checks_num += 1
        if self.checks_num > 15 or (datetime.datetime.now() - self.last_check > datetime.timedelta(seconds=60 * 5)):
            self.srv_addr = None
            self.checks_num = 0

        if self.srv_addr is None:
            # srv_addr = self._get_srv_addr()  # TODO
            pass
        else:
            srv_addr = None

        if srv_addr is not None and srv_addr != current_addr:
            self.srv_addr = srv_addr

        return self.srv_addr

    def _get_srv_addr(self):
        # TODO
        return None

    def _ensure_srv_address(self):
        if self.srv_addr is None:
            self._establish_connection()

    def _establish_connection(self):
        raise NotImplementedError

    def report_host_info(self, host_info):
        self._ensure_srv_address()

        request = {'address': self.my_addr,
                   'msg': consts.AGENT_MSG_HOST_INFO,
                   'info': host_info}

        response = _send_http_request(self.srv_addr, request)

        cfg_changes = {}
        if 'cfg' in response:
            cfg_changes = config.merge(response['cfg'])

        return response, cfg_changes

    def get_job(self):
        self._ensure_srv_address()

        request = {'address': self.my_addr, 'msg': consts.AGENT_MSG_GET_JOB}

        response = _send_http_request(self.srv_addr, request)

        cfg_changes = {}
        if 'cfg' in response:
            cfg_changes = config.merge(response['cfg'])

        version = None
        if 'version' in response:
            version = response['version']

        if 'job' in response:
            return response['job'], cfg_changes, version

        return {}, cfg_changes, version

    def get_job_step(self):
        self._ensure_srv_address()

        request = {'address': self.my_addr, 'msg': consts.AGENT_MSG_GET_JOB_STEP}

        response = _send_http_request(self.srv_addr, request)

        if 'job_step' in response:
            return response['job_step']

        return {}

    def report_step_result(self, job_id, step_idx, result):
        request = {'address': self.my_addr,
                   'msg': consts.AGENT_MSG_STEP_RESULT2,
                   'job_id': job_id,
                   'step_idx': step_idx,
                   'result': result}

        log.info('job %s step %s report %s', job_id, step_idx, result)
        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        return response

    def dispatch_tests(self, job_id, step_idx, tests):
        request = {'address': self.my_addr,
                   'msg': consts.AGENT_MSG_DISPATCH_TESTS,
                   'job_id': job_id,
                   'step_idx': step_idx,
                   'tests': tests}

        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        return response

    def keep_alive(self, job_id=None):
        request = {'address': self.my_addr,
                   'msg': consts.AGENT_MSG_KEEP_ALIVE,
                   'job_id': job_id}

        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        return response
