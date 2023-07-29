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
import re
import json
import time
import shlex
import zipfile
import asyncio
import logging
import traceback
try:
    import pylxd
except ImportError:
    pylxd = None

from . import consts
from . import utils
from . import miniobase


log = logging.getLogger(__name__)


def detect_capabilities():
    if pylxd is None:
        return {}
    try:
        client = pylxd.Client()
        info = client.host_info
        return {'lxd': info['environment']['server_version']}
    except Exception:
        return {}


class Timeout(Exception):
    pass


class LxdExecContext:
    def __init__(self, job):
        self.job = job

        self.client = None
        self.lab_net = None
        self.cntr = None
        self.logs = []

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
        self._async_run('chmod a+x kktool', deadline, cwd='.')
        logs = self._async_run('cat /etc/os-release', deadline)
        m = re.search('^ID="?(.*?)"?$', logs, re.M)
        distro = m.group(1).lower()
        m = re.search('^VERSION="?(.*?)"?$', logs, re.M)
        distro_ver = m.group(1).lower()
        if distro in ['debian', 'ubuntu']:
            self._async_run('apt-get update', deadline)
            self._async_run('apt-get install -y python3', deadline)
        elif distro == 'centos':
            time.sleep(3)  # wait for network
            if distro_ver == '8':
                self._async_run('dnf install -y python39', deadline)
        elif distro in ['fedora', 'rocky']:
            time.sleep(3)  # wait for network
            self._async_run('yum install -y python3', deadline)
        elif 'suse' in distro:
            time.sleep(3)  # wait for network
            self._async_run('zypper install -y curl python39 sudo system-group-wheel', deadline)
            self._async_run('ln -sf /usr/bin/python3.9 /usr/bin/python3', deadline)

    def start(self, timeout):
        try:
            self._start(timeout)
        except Timeout:
            exc = traceback.format_exc()
            log.exception('problem with starting or initializing container')
            self.stop()
            return {'status': 'error', 'reason': 'job-timeout', 'msg': exc}
        except Exception:
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
            except Exception:
                log.exception('IGNORED EXCEPTION')
            try:
                self.cntr.delete(wait=True)
            except Exception:
                log.exception('IGNORED EXCEPTION')

    def get_return_ip_addr(self):
        return self.lab_net.config['ipv4.address'].split('/')[0]

    def _stdout_handler(self, chunk):
        if not isinstance(chunk, str):
            chunk = chunk.decode()

        self.logs.append(chunk)

        log.info(chunk.rstrip())

    def _async_run(self, cmd, deadline, cwd='/', env=None):
        logs, exit_code = asyncio.run(self._lxd_run(cmd, cwd, deadline, env))
        if exit_code != 0:
            t0, t1, timeout = utils.get_times(deadline)
            raise Exception("non-zero %d exit code from '%s', cwd:%s, now:%s, deadline:%s, time: %ds" % (
                exit_code, cmd, str(cwd), t0, t1, timeout))
        return logs

    async def _lxd_run(self, cmd, cwd, deadline, env=None):  # pylint: disable=unused-argument
        log.info('cmd %s', cmd)
        self.logs = []
        cmd = shlex.split(cmd)
        result = self.cntr.execute(cmd, environment=env, stdout_handler=self._stdout_handler,
                                   stderr_handler=self._stdout_handler)
        log.info('EXIT: %s', result.exit_code)
        return ''.join(self.logs), result.exit_code

    async def _async_run_exc(self, proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        lxd_cwd = '/root'

        # upload step file
        dest_step_file_path = os.path.join(lxd_cwd, os.path.basename(step_file_path))
        with open(step_file_path, 'rb') as f:
            filedata = f.read()
        self.cntr.files.put(dest_step_file_path, filedata)

        # upload step tool if it is not built-in tool
        pypath, mod = tool_path
        if pypath:
            if pypath.startswith('minio:'):
                # copy tool from minio to lxd container
                tool_zip, tool_bucket, tool_ver = miniobase.download_tool(step, pypath)
                tool_dest = os.path.join('/', tool_bucket, tool_ver)
            else:
                # copy local tool to lxd container
                tool_zip = os.path.join(pypath, 'tool.zip')
                with zipfile.ZipFile(tool_zip, "w") as pz:
                    for root, _, files in os.walk(pypath):
                        for name in files:
                            if name.endswith(('.pyc', '~')):
                                continue
                            if name == 'tool.zip':
                                continue
                            p = os.path.join(root, name)
                            n = os.path.relpath(p, pypath)
                            pz.write(p, arcname=n)
                tool_dest = os.path.join('/', step['tool'])

            cmd = 'mkdir -p %s' % tool_dest
            await self._lxd_run(cmd, '/', 10)
            cmd = 'chmod a+w %s' % tool_dest
            await self._lxd_run(cmd, '/', 10)

            tool_dest_file = os.path.join(tool_dest, 'tool.zip')
            with open(tool_zip, "rb") as tf:
                filedata = tf.read()
                self.cntr.files.put(tool_dest_file, filedata)

            mod = '%s/tool.zip:%s' % (tool_dest, mod)

        cmd = "%s/kktool -m %s -r %s -s %s %s" % (lxd_cwd, mod, return_addr, dest_step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, lxd_cwd, timeout)

        if 'branch_env' in step and step['branch_env']:
            env = step['branch_env']
        else:
            env = None

        # setup log context
        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)

        deadline = time.time() + timeout
        try:
            await self._lxd_run(cmd, lxd_cwd, deadline, env=env)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if proc_coord.result == {}:
                proc_coord.result = {'status': 'error', 'reason': 'job-timeout'}


    async def async_run(self, proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        try:
            await self._async_run_exc(proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user)
        except Exception:
            log.exception('passing up')
            raise
