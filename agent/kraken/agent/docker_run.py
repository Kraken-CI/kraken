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
import re
import time
import json
import struct
import asyncio
import tarfile
import logging
import traceback

from . import consts, utils

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
    except Exception:
        return {}


def _create_archive(filepath, arcname=None):
    if arcname is None:
        arcname = filepath
    data = io.BytesIO()
    with tarfile.TarFile(fileobj=data, mode='w') as archive:
        archive.add(filepath, arcname=arcname)
    data.seek(0)
    return data


class Timeout(Exception):
    pass


class DockerExecContext:
    def __init__(self, job):
        self.job = job

        self.client = None
        self.cntr = None
        self.lab_net = None
        self.curr_cntr = None
        self.clickhouse_ip = None
        self.minio_ip = None
        self.swarm = False

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

    def _start(self, timeout):
        self.client = docker.from_env()

        if self.client.swarm.id is not None:
            self.swarm = True
            log.info('docker swarm present: %s', self.client.swarm.id)
        else:
            log.info('docker swarm not present')

        dkr_sock = '/var/run/docker.sock'

        # prepare list of mounts from host agent container
        mounts = []
        dkr_sock_mounted = False
        if utils.is_in_docker():
            # get current container with agent
            curr_cntr_id = os.environ['HOSTNAME']
            self.curr_cntr = self.client.containers.get(curr_cntr_id)

            for mnt in self.curr_cntr.attrs['Mounts']:
                mnt2 = docker.types.Mount(target=mnt['Destination'], source=mnt['Source'], type=mnt['Type'])
                mounts.append(mnt2)
                if mnt['Destination'] == dkr_sock:
                    dkr_sock_mounted = True

        image = self.job['system']
        log.info('starting container %s, mounts: %s', image, mounts)
        volumes = None
        if os.path.exists(dkr_sock) and not dkr_sock_mounted:
            volumes = {dkr_sock: {'bind': dkr_sock, 'mode': 'rw'}}
        self.cntr = self.client.containers.run(image, 'sleep %d' % (int(timeout) + 60), detach=True, mounts=mounts, volumes=volumes)
        log.info('docker container %s', self.cntr.id)

        archive = _create_archive(os.path.realpath(os.path.join(consts.AGENT_DIR, 'kktool')), arcname='kktool')
        self.cntr.put_archive('/', archive)

        deadline = time.time() + timeout
        logs = self._async_run('cat /etc/os-release', deadline)
        m = re.search('^ID="?(.*?)"?$', logs, re.M)
        distro = m.group(1).lower()
        #m = re.search('^VERSION_ID="(.*)"$', logs, re.M)
        #version = m.group(1)
        self._async_run("ls -al %s" % dkr_sock, deadline)
        if distro in ['debian', 'ubuntu']:
            self._async_run('apt-get update', deadline)
            self._async_run('apt-get install -y --no-install-recommends locales openssh-client '
                           'ca-certificates sudo git unzip zip gnupg curl wget make net-tools '
                           'python3 python3-pytest python3-venv python3-docker python3-setuptools',
                           deadline)
            self._async_run('ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime', deadline)
            self._async_run('locale-gen en_US.UTF-8', deadline)
            try:
                self._async_run('getent passwd kraken', deadline)
            except Exception:
                self._async_run('useradd kraken -d /opt/kraken -m -s /bin/bash -G sudo', deadline)
            self._async_run('echo "kraken ALL=NOPASSWD: ALL" > /etc/sudoers.d/kraken', deadline)
            self._async_run('echo \'Defaults    env_keep += "DEBIAN_FRONTEND"\' > /etc/sudoers.d/kraken_env_keep', deadline)
            if os.path.exists(dkr_sock):
                dkr_gid = self._async_run("stat -c '%%g' %s" % dkr_sock, deadline)
                self._async_run("addgroup --gid %d docker" % int(dkr_gid.strip()), deadline)
        elif distro in ['centos', 'fedora', 'rocky']:
            pkgs = ('openssh-clients ca-certificates sudo git unzip zip gnupg curl wget make net-tools ' +
                    'python3 python3-pytest python3-virtualenv python3-setuptools')
            if distro == 'fedora':
                pkgs += ' python3-docker'
            self._async_run('yum install -y ' + pkgs, deadline)
            if distro in ['centos', 'rocky']:
                self._async_run('python3 -m pip install docker-py', deadline)
            try:
                self._async_run('getent passwd kraken', deadline)
            except Exception:
                self._async_run('useradd kraken -d /opt/kraken -m -s /bin/bash -G wheel --system', deadline)
            self._async_run('echo "kraken ALL=NOPASSWD: ALL" > /etc/sudoers.d/kraken', deadline)
            if os.path.exists(dkr_sock):
                dkr_gid = self._async_run("stat -c '%%g' %s" % dkr_sock, deadline)
                self._async_run("groupadd --gid %d docker" % int(dkr_gid.strip()), deadline)
        if os.path.exists(dkr_sock):
            self._async_run('usermod -G docker kraken', deadline)

        # if agent is running inside docker then get or create lab_net and use it to communicate with execution container
        if utils.is_in_docker():
            log.info('docker networks:')
            for net in self.client.networks.list():
                log.info('  net: %s', net.name)
                if net.name.endswith('lab_net'):
                    self.lab_net = net
                    break
            if self.lab_net is None:
                if self.swarm:
                    driver = 'overlay'
                    lab_net_name = 'kraken_lab_net'
                else:
                    driver = 'bridge'
                    lab_net_name = 'lab_net'
                self.lab_net = self.client.networks.create(lab_net_name, driver=driver, attachable=True)

            # connect new container to lab_net
            try:
                self.lab_net.connect(self.cntr)
            except Exception as ex:
                if 'address already in use' in str(ex).lower():
                    log.warning('address already in use')
                else:
                    log.exception('problems with lab_net')
                    raise

            # connect current container with agent to lab_net
            if self.lab_net.name not in self.curr_cntr.attrs['NetworkSettings']['Networks']:
                self.lab_net.connect(self.curr_cntr)
                self.curr_cntr.reload()
            log.info('container networks:')
            for net_name, net in self.curr_cntr.attrs['NetworkSettings']['Networks'].items():
                log.info('%s: %s', net_name, net['IPAddress'])

            # # connect clickhouse and minio to lab_net
            # for c in self.client.containers.list():
            #     if 'clickhouse' in c.name or 'minio' in c.name:
            #         if self.lab_net.name not in c.attrs['NetworkSettings']['Networks']:
            #             self.lab_net.connect(c)
            #         c.reload()
            #         if 'clickhouse' in c.name:
            #             self.clickhouse_ip = c.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']
            #         if 'minio' in c.name:
            #             self.minio_ip = c.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']

    def get_return_ip_addr(self):
        if self.curr_cntr:
            addr = self.curr_cntr.attrs['NetworkSettings']['Networks'][self.lab_net.name]['IPAddress']
            return addr
        # TODO: in case of running agent not in container then IP address is hardcoded;
        # would be good to get it in runtime
        return '172.17.0.1'

    def stop(self):
        log.info('stopping container %s', self.cntr)
        if self.cntr:
            try:
                self.cntr.kill()
            except Exception:
                log.exception('IGNORED EXCEPTION')
            try:
                self.cntr.remove()
            except Exception:
                log.exception('IGNORED EXCEPTION')

    def _async_run(self, cmd, deadline, cwd='/', user='root'):
        logs, exit_code = asyncio.run(self._dkr_run(None, cmd, cwd, deadline, user))
        if exit_code != 0:
            t0, t1, timeout = utils.get_times(deadline)
            raise Exception("non-zero %d exit code from '%s', cwd:%s, user:%s, now:%s, deadline:%s, time: %ds" % (
                exit_code, cmd, str(cwd), str(user), t0, t1, timeout))
        return logs

    async def _dkr_run(self, proc_coord, cmd, cwd, deadline, user, log_ctx=None):
        t0, t1, timeout = utils.get_times(deadline)
        log.info("cmd '%s' in '%s', now %s, deadline %s, time: %ds", cmd, cwd, t0, t1, timeout)

        if log_ctx:
            log.set_ctx(**log_ctx)

        exe = self.cntr.client.api.exec_create(self.cntr.id, cmd, workdir=cwd, user=user)
        sock = self.cntr.client.api.exec_start(exe['Id'], socket=True)

        logs = ''
        logs_to_print = ''

        # Read output from command from docker. Stream returned from docker needs
        # to be parsed according to its format: https://docs.docker.com/engine/api/v1.39/#operation/ContainerAttach
        reader, _ = await asyncio.open_unix_connection(sock=sock._sock)   # pylint: disable=protected-access
        buff = b''
        eof = False
        t0 = time.time()
        while not eof:
            while len(buff) < 8:
                buff_frag = await reader.read(8 - len(buff))
                if not buff_frag:
                    eof = True
                    break
                buff += buff_frag
            if eof:
                break
            header = buff[:8]
            buff = buff[8:]
            # parse docker header
            _, size = struct.unpack('>BxxxL', header)
            if size <= 0:
                break
            chunk = buff[:size]
            buff = buff[size:]
            needed_size = size - len(chunk)
            while needed_size > 0:
                buff_frag = await reader.read(needed_size)
                if not buff_frag:
                    eof = True
                    break
                buff += buff_frag
                frag = buff[:needed_size]
                chunk += frag
                buff = buff[len(frag):]
                needed_size = size - len(chunk)
            log_frag = chunk.decode()

            logs += log_frag
            logs_to_print += log_frag

            # send logs if they are bigger than 1k or every 3 seconds
            t1 = time.time()
            if len(logs_to_print) > 1024 or t1 - t0 > 3:
                t0 = t1
                # print read lines, any reminder leave in logs_to_print for next iteration
                lines = logs_to_print.rsplit('\n', 1)
                if len(lines) == 2:
                    log.info(lines[0])
                    logs_to_print = lines[1]
                else:
                    logs_to_print = lines[0]

            # check deadline
            if time.time() > deadline:
                if logs_to_print:
                    log.info(logs_to_print)
                raise Timeout

            # check cancel
            if proc_coord and proc_coord.is_canceled:
                break

        # trace the rest of logs
        if logs_to_print:
            log.info(logs_to_print)

        if log_ctx:
            log.reset_ctx()

        if proc_coord and proc_coord.is_canceled:
            exit_code = 10001
            log.info('CANCELED')
        else:
            exit_code = self.cntr.client.api.exec_inspect(exe['Id'])['ExitCode']
            while exit_code is None:
                await asyncio.sleep(0)
                exit_code = self.cntr.client.api.exec_inspect(exe['Id'])['ExitCode']
            log.info('EXIT: %s', exit_code)
        return logs, exit_code

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        docker_cwd = '/opt/kraken'
        archive = _create_archive(step_file_path, os.path.basename(step_file_path))
        self.cntr.put_archive('/', archive)

        mod = tool_path.split()[-1]
        step_file_path2 = os.path.join('/', os.path.basename(step_file_path))
        cmd = "/kktool -m %s -r %s -s %s %s" % (mod, return_addr, step_file_path2, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, docker_cwd, timeout)

        if not user:
            user = 'kraken'

        # setup log context
        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)
        log_ctx = dict(job=step['job_id'], step=step['index'], tool=step['tool'])

        # run tool
        deadline = time.time() + timeout
        try:
            await self._dkr_run(proc_coord, cmd, docker_cwd, deadline, user, log_ctx)
        except Timeout:
            if proc_coord.result == {}:
                t0, t1, timeout = utils.get_times(deadline)
                log.info('job time expired, now: %s, deadline: %s', t0, t1)
                proc_coord.result = {'status': 'error', 'reason': 'job-timeout'}

        log.reset_ctx()
