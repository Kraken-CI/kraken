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
import shlex
import asyncio
import logging
import traceback
try:
    import pylxd
except ImportError:
    pylxd = None

from . import consts


log = logging.getLogger(__name__)


def detect_capabilities():
    if pylxd is None:
        return {}
    try:
        client = pylxd.Client()
        info = client.host_info
        return {'lxd': info['environment']['server_version']}
    except:
        return {}


class Timeout(Exception):
    pass


class LxdExecContext:
    def __init__(self, job):
        self.job = job

        self.client = None
        self.lab_net = None
        self.cntr = None
        self.log_ctx = None

    def _start(self, timeout):
        self.client = pylxd.Client()

        # prepare network for container
        for net in self.client.networks.all():
            if net.name.endswith('lab_net'):
                self.lab_net = net
                break
        if self.lab_net is None:
            self.lab_net = self.client.networks.create('lab_net')

        # prepare container definition
        image = self.job['system']
        config = {'name': 'kktool-%d' % self.job['id'],
                  'source': {'type': 'image',
                             "mode": "pull",
                             #"server": "https://cloud-images.ubuntu.com/daily",
                             "server": "https://images.linuxcontainers.org:8443", # https://images.linuxcontainers.org/
                             "protocol": "simplestreams",
                             'alias': image},
                  "devices": {
		      "lab_net": {
			  "nictype": "bridged",
			  "parent": "lab_net",
			  "type": "nic"
		      }
		  },
        }
        log.info('lxd container config: %s', config)
        self.cntr = self.client.containers.create(config, wait=True)
        self.cntr.start(wait=True)
        log.info('lxd container %s', self.cntr.name)
        for _ in range(100):
            if self.cntr.status != 'Running':
                time.sleep(0.1)
                self.cntr.sync()
                log.info('container status %s', self.cntr.status)
        if self.cntr.status != 'Running':
            self.stop()
            raise Exception('cannot start container')

        kktool_path = os.path.realpath(os.path.join(consts.AGENT_DIR, 'kktool'))
        with open(kktool_path, 'rb') as f:
            filedata = f.read()
        self.cntr.files.put('/root/kktool', filedata)

        deadline = time.time() + timeout
        asyncio.run(self._lxd_run('chmod a+x kktool', '.', deadline))
        asyncio.run(self._lxd_run('apt-get update', '/', deadline))
        asyncio.run(self._lxd_run('apt-get install -y python3', '/', deadline))

    def start(self, timeout):
        try:
            self._start(timeout)
        except Timeout:
            exc = traceback.format_exc()
            log.exception('problem with starting or initializing container')
            self.stop()
            return {'status': 'error', 'reason': 'job-timeout', 'msg': exc}
        except:
            exc = traceback.format_exc()
            log.exception('problem with starting or initializing container')
            self.stop()
            return {'status': 'error', 'reason': 'exception', 'msg': exc}
        return None

    def stop(self):
        log.info('stopping container %s', self.cntr)
        if self.cntr:
            try:
                self.cntr.stop(wait=True)
            except:
                log.exception('IGNORED EXCEPTION')
            try:
                self.cntr.delete(wait=True)
            except:
                log.exception('IGNORED EXCEPTION')

    def get_return_ip_addr(self):
        return self.lab_net.config['ipv4.address'].split('/')[0]

    def _stdout_handler(self, chunk):
        if not isinstance(chunk, str):
            chunk = chunk.decode()

        if self.log_ctx:
            log.set_ctx(**self.log_ctx)

        log.info(chunk.rstrip())

        if self.log_ctx:
            log.reset_ctx()

    async def _lxd_run(self, cmd, cwd, deadline, env=None):  # pylint: disable=unused-argument
        log.info('cmd %s', cmd)
        cmd = shlex.split(cmd)
        result = self.cntr.execute(cmd, environment=env, stdout_handler=self._stdout_handler,
                                   stderr_handler=self._stdout_handler)
        log.info('EXIT: %s', result.exit_code)

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        lxd_cwd = '/root'

        # upload steop file
        dest_step_file_path = os.path.join(lxd_cwd, os.path.basename(step_file_path))
        with open(step_file_path, 'rb') as f:
            filedata = f.read()
        self.cntr.files.put(dest_step_file_path, filedata)

        mod = tool_path.split()[-1]
        cmd = "%s/kktool -m %s -r %s -s %s %s" % (lxd_cwd, mod, return_addr, dest_step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, lxd_cwd, timeout)

        # setup log context
        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)
        self.log_ctx = dict(job=step['job_id'], step=step['index'], tool=step['tool'])

        deadline = time.time() + timeout
        try:
            await self._lxd_run(cmd, lxd_cwd, deadline)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if proc_coord.result == {}:
                proc_coord.result = {'status': 'error', 'reason': 'job-timeout'}

        self.log_ctx = None
