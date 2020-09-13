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
import io
import time
import asyncio
import tarfile
import logging

from . import consts

try:
    import docker
except ImportError:
    docker = None

log = logging.getLogger(__name__)


def detect_capabilities():
    if docker is None:
        return {}
    try:
        client = docker.from_env()
        ver = client.version()
        return {'docker': ver['Version']}
    except:
        return {}


def _create_archive(filepath, arcname=None):
    if arcname is None:
        arcname = filepath
    data = io.BytesIO()
    with tarfile.TarFile(fileobj=data, mode='w') as archive:
        archive.add(filepath, arcname=arcname)
    data.seek(0)
    return data


def _is_docker():
    with open('/proc/self/cgroup', 'r') as procfile:
        for line in procfile:
            fields = line.strip().split('/')
            if 'docker' in fields[1]:
                return True
    return False


class Timeout(Exception):
    pass


class DockerExecContext:
    def __init__(self, job):
        self.job = job

        self.client = None
        self.cntr = None
        self.lab_net = None
        self.curr_cntr = None
        self.logstash_ip = None
        self.storage_ip = None
        self.swarm = False

    def start(self, timeout):
        self.client = docker.from_env()

        if self.client.swarm.id is not None:
            self.swarm = True
            log.info('docker swarm present: %s', self.client.swarm.id)
        else:
            log.info('docker swarm not present')

        image = self.job['system']
        self.cntr = self.client.containers.run(image, 'sleep %d' % int(timeout), detach=True)
        log.info('docker container %s', self.cntr.id)

        archive = _create_archive(os.path.realpath(os.path.join(consts.AGENT_DIR, 'kktool')), arcname='kktool')
        self.cntr.put_archive('/', archive)

        deadline = time.time() + timeout
        asyncio.run(self._dkr_run('apt-get update', '/', deadline, None, 'root'))
        asyncio.run(self._dkr_run('apt-get install -y python3', '/', deadline, None, 'root'))

        # if agent is running inside docker then get or create lab_net and use it to communicate with execution container
        if _is_docker():
            for net in self.client.networks.list():
                if net.name.endswith('lab_net'):
                    self.lab_net = net
                    break
            if self.lab_net is None:
                if self.swarm:
                    driver = 'overlay'
                else:
                    driver = 'bridge'
                self.lab_net = self.client.networks.create('lab_net', driver=driver, attachable=True)

            # connect new container to lab_net
            try:
                self.lab_net.connect(self.cntr)
            except:
                log.exception('problems with lab_net')
                raise

            # get current container with agent
            curr_cntr_id = os.environ['HOSTNAME']
            self.curr_cntr = self.client.containers.get(curr_cntr_id)

            # connect current container with agent to lab_net
            if self.lab_net.name not in self.curr_cntr.attrs['NetworkSettings']['Networks']:
                self.lab_net.connect(self.curr_cntr)
                self.curr_cntr.reload()

            # connect logstash and storage to lab_net
            for c in self.client.containers.list():
                if 'logstash' in c.name or 'storage' in c.name:
                    if self.lab_net.name not in c.attrs['NetworkSettings']['Networks']:
                        self.lab_net.connect(c)
                    c.reload()
                    if 'logstash' in c.name:
                        self.logstash_ip = c.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']
                    if 'storage' in c.name:
                        self.storage_ip = c.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']

    def get_return_ip_addr(self):
        if self.curr_cntr:
            addr = self.curr_cntr.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']
            log.info('get_return_ip_addr curr_cntr %s %s', self.curr_cntr, addr)
            return addr
        # TODO: in case of running agent not in container then IP address is hardcoded;
        # would be good to get it in runtime
        return '172.17.0.1'

    def stop(self):
        try:
            self.cntr.kill()
        except:
            # TODO: add some ignore trace here
            pass
        try:
            self.cntr.remove()
        except:
            # TODO: add some ignore trace here
            pass

    async def _dkr_run(self, cmd, cwd, deadline, env, user):
        log.info('cmd %s, time %s, deadline %s', cmd, time.time(), deadline)
        exe = self.cntr.client.api.exec_create(self.cntr.id, cmd, workdir=cwd, environment=env, user=user)
        stream = self.cntr.client.api.exec_start(exe['Id'], stream=True)
        for chunk in stream:
            log.info(chunk.decode().rstrip())
            await asyncio.sleep(0)
            if time.time() > deadline:
                raise Timeout
        exit_code = self.cntr.client.api.exec_inspect(exe['Id'])['ExitCode']
        while exit_code is None:
            await asyncio.sleep(0)
            exit_code = self.cntr.client.api.exec_inspect(exe['Id'])['ExitCode']
        log.info('EXIT: %s', exit_code)

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        docker_cwd = None
        archive = _create_archive(step_file_path, os.path.basename(step_file_path))
        self.cntr.put_archive('/', archive)

        mod = tool_path.split()[-1]
        step_file_path = os.path.join('/', os.path.basename(step_file_path))
        cmd = "/kktool -m %s -r %s -s %s %s" % (mod, return_addr, step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, docker_cwd, timeout)

        env = {}

        # pass address to logstash via env
        if self.logstash_ip:
            logstash_addr = '%s:%s' % (self.logstash_ip, os.environ.get(
                'KRAKEN_LOGSTASH_PORT', consts.DEFAULT_LOGSTASH_PORT))
            env['KRAKEN_LOGSTASH_ADDR'] = logstash_addr
        elif 'KRAKEN_LOGSTASH_ADDR' in os.environ:
            env['KRAKEN_LOGSTASH_ADDR'] = os.environ['KRAKEN_LOGSTASH_ADDR']

        # pass address to storage via env
        if self.storage_ip:
            port = consts.DEFAULT_STORAGE_ADDR.split(':')[1]
            storage_addr = '%s:%s' % (self.storage_ip, port)
            env = {'KRAKEN_STORAGE_ADDR': storage_addr}
        elif 'KRAKEN_STORAGE_ADDR' in os.environ:
            env = {'KRAKEN_STORAGE_ADDR': os.environ['KRAKEN_STORAGE_ADDR']}

        if not env:
            env = None

        if not user:
            user = 'kraken'

        deadline = time.time() + timeout
        try:
            await self._dkr_run(cmd, docker_cwd, deadline, env, user)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if proc_coord.result == {}:
                log.info('timout expired')
                proc_coord.result = {'status': 'error', 'reason': 'timeout'}
