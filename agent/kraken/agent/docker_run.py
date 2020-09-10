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
        self.kknet = None
        self.curr_cntr = None
        self.logstash_ip = None
        self.swarm = False

    def start(self, timeout):
        self.client = docker.from_env()

        if self.client.swarm.id is not None:
            self.swarm = True
            log.info('docker swarm present: %s', self.client.swarm.id)
        else:
            log.info('docker swarm not present')

        image = self.job['system']
        self.cntr = self.client.containers.run(image, 'sleep 10000', detach=True)
        log.info('docker container %s', self.cntr.id)

        archive = _create_archive(os.path.realpath(os.path.join(consts.AGENT_DIR, 'kktool')), arcname='kktool')
        self.cntr.put_archive('/root', archive)

        deadline = time.time() + timeout
        asyncio.run(self._dkr_run('apt-get update', '/', deadline))
        asyncio.run(self._dkr_run('apt-get install -y python3', '/', deadline))

        # if agent is running inside docker then get or create kknet and use it to communicate with execution container
        if _is_docker():
            if self.swarm:
                try:
                    self.kknet = self.client.networks.get('kknet')
                except:
                    self.kknet = self.client.networks.create('kknet', driver='overlay', attachable=True)

                # connect new container to kknet
                try:
                    self.kknet.connect(self.cntr)
                except:
                    log.exception('problems with kknet')
                    raise

            # get current container with agent
            curr_cntr_id = os.environ['HOSTNAME']
            self.curr_cntr = self.client.containers.get(curr_cntr_id)

            if self.swarm:
                # connect current container with agent to kknet
                if 'kknet' not in self.curr_cntr.attrs['NetworkSettings']['Networks']:
                    self.kknet.connect(self.curr_cntr)
                    self.curr_cntr.reload()

                # connect logstash to kknet
                for c in self.client.containers.list():
                    if 'logstash' in c.name:
                        if 'kknet' not in c.attrs['NetworkSettings']['Networks']:
                            self.kknet.connect(c)
                        c.reload()
                        self.logstash_ip = c.attrs['NetworkSettings']['Networks']['kknet']['IPAddress']

    def get_return_ip_addr(self):
        log.info('get_return_ip_addr')
        if self.curr_cntr:
            log.info('get_return_ip_addr curr_cntr %s', self.curr_cntr)
            if self.swarm:
                log.info('get_return_ip_addr SWARM ADDR %s', self.curr_cntr.attrs['NetworkSettings']['Networks']['kknet']['IPAddress'])
                return self.curr_cntr.attrs['NetworkSettings']['Networks']['kknet']['IPAddress']
            else:
                # look for address in lab_net
                for net_name, net in self.curr_cntr.attrs['NetworkSettings']['Networks'].items():
                    if net_name.endswith('lab_net'):
                        log.info('get_return_ip_addr COMP ADDR %s', net['IPAddress'])
                        return net['IPAddress']
                # if not found then just pick first one
                nets = list(self.curr_cntr.attrs['NetworkSettings']['Networks'].values())
                if len(nets) > 0:
                    return nets[0]['IPAddress']
                raise Exception('cannot determine container IP address: %s' % str(self.curr_cntr.attrs['NetworkSettings']['Networks']))
        # TODO: in case of running agent not in container then IP address is hardcoded;
        # would be good to get it in runtime
        log.info('get_return_ip_addr ADDR HARDCODED')
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

    async def _dkr_run(self, cmd, cwd, deadline, env=None, user=''):
        log.info('cmd %s', cmd)
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

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout):  # pylint: disable=unused-argument
        docker_cwd = '/root'
        archive = _create_archive(step_file_path, os.path.basename(step_file_path))
        self.cntr.put_archive(docker_cwd, archive)

        mod = tool_path.split()[-1]
        step_file_path = os.path.join(docker_cwd, os.path.basename(step_file_path))
        cmd = "%s/kktool -m %s -r %s -s %s %s" % (docker_cwd, mod, return_addr, step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, docker_cwd, timeout)

        # pass address to logstash via env
        if self.logstash_ip:
            logstash_addr = '%s:%s' % (self.logstash_ip, os.environ.get(
                'KRAKEN_LOGSTASH_PORT', consts.DEFAULT_LOGSTASH_PORT))
            env = {'KRAKEN_LOGSTASH_ADDR': logstash_addr}
        elif 'KRAKEN_LOGSTASH_ADDR' in os.environ:
            env = {'KRAKEN_LOGSTASH_ADDR': os.environ['KRAKEN_LOGSTASH_ADDR']}
        else:
            env = None

        deadline = time.time() + timeout
        try:
            await self._dkr_run(cmd, docker_cwd, deadline, env, user='')
        except Timeout:
            # TODO: it should be better handled but needs testing
            if proc_coord.result == {}:
                proc_coord.result = {'status': 'error', 'reason': 'timeout'}
