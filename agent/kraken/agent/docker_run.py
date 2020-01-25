import os
import io
import time
import asyncio
import tarfile
import logging
import ipaddress
import netifaces

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


class Timeout(Exception): pass


class DockerExecContext:
    def __init__(self, job):
        self.job = job

    def start(self, timeout):
        self.client = docker.from_env()

        image = self.job['system']
        self.cntr = self.client.containers.run(image, 'sleep 10000', detach=True)
        log.info('docker container %s', self.cntr.id)

        archive = _create_archive('kktool')
        self.cntr.put_archive('/root', archive)

        deadline = time.time() + timeout
        asyncio.run(self._dkr_run('apt-get update', '/', deadline))
        asyncio.run(self._dkr_run('apt-get install -y python3', '/', deadline))

        # get or create kknet
        try:
            self.kknet = self.client.networks.get('kknet')
        except:
            self.kknet = self.client.networks.create('kknet', driver='overlay', attachable=True)

        # connect new container to kknet
        try:
            self.kknet.connect(self.cntr)
        except:
            log.exception('IGNORED EXCEPTION')
            raise

        # connect current container to kknet
        self.curr_cntr = None
        try:
            curr_cntr_id = os.environ['HOSTNAME']
            self.curr_cntr = self.client.containers.get(curr_cntr_id)
            if 'kknet' not in self.curr_cntr.attrs['NetworkSettings']['Networks']:
                self.kknet.connect(self.curr_cntr)
                self.curr_cntr.reload()
        except:
            log.exception('IGNORED EXCEPTION')

        # connect logstash to kknet
        self.logstash_ip = None
        for c in self.client.containers.list():
            if 'logstash' in c.name:
                if 'kknet' not in c.attrs['NetworkSettings']['Networks']:
                    self.kknet.connect(c)
                c.reload()
                self.logstash_ip = c.attrs['NetworkSettings']['Networks']['kknet']['IPAddress']


    def get_return_ip_addr(self):
        if self.curr_cntr:
            return self.curr_cntr.attrs['NetworkSettings']['Networks']['kknet']['IPAddress']
        # TODO: add support when agent is not run in docker
        raise Exception('cannot find ip address')

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

    async def _dkr_run(self, cmd, cwd, deadline, env=None):
        log.info('cmd %s', cmd)
        exe = self.cntr.client.api.exec_create(self.cntr.id, cmd, workdir=cwd, environment=env)
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

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout):
        docker_cwd = '/root'
        archive = _create_archive(step_file_path, os.path.basename(step_file_path))
        self.cntr.put_archive(docker_cwd, archive)

        mod = tool_path.split()[-1]
        step_file_path = os.path.join(docker_cwd, os.path.basename(step_file_path))
        cmd = "%s/kktool -m %s -r %s -s %s %s" % (docker_cwd, mod, return_addr, step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, docker_cwd, timeout)

        # pass address to logstash via env
        if self.logstash_ip:
            logstash_addr = '%s:%s' % (self.logstash_ip, os.environ.get('KRAKEN_LOGSTASH_PORT', consts.DEFAULT_LOGSTASH_PORT))
            env = {'KRAKEN_LOGSTASH_ADDR': logstash_addr}
        elif 'KRAKEN_LOGSTASH_ADDR' in os.environ:
            env = {'KRAKEN_LOGSTASH_ADDR': os.environ['KRAKEN_LOGSTASH_ADDR']}
        else:
            env = None

        deadline = time.time() + timeout
        try:
            await self._dkr_run(cmd, docker_cwd, deadline, env)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if proc_coord.result == {}:
                proc_coord.result = {'status': 'error', 'reason': 'timeout'}


def main():
    asyncio.run(run("ubuntu:19.04", "-h"))


if __name__ == '__main__':
    main()
