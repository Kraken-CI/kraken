import os
import io
import time
import shlex
import asyncio
import tarfile
import logging
try:
    import pylxd
except ImportError:
    pylxd = None


log = logging.getLogger(__name__)


def detect_capabilities():
    if pylxd is None:
        return {}
    try:
        client = pylxd.Client()
        info = client.host_info
        return {'lxd': info['server_version']}
    except:
        return {}


class Timeout(Exception): pass


class DockerExecContext:
    def __init__(self, job):
        self.job = job

    def start(self, timeout):
        import docker
        self.client = pylxd.Client()

        image = self.job['system']  # 'bionic/amd64'
        config = {'name': 'kktool', 'source': {'type': 'image',
                                               "mode": "pull",
                                               "server": "https://cloud-images.ubuntu.com/daily",
                                               "protocol": "simplestreams",
                                               'alias': image}}
        self.cntr = self.client.containers.create(config, wait=True)
        self.cntr.start()
        log.info('docker container %s', self.cntr.id)

        archive = _create_archive('kktool')
        self.cntr.put_archive('/root', archive)

        deadline = time.time() + timeout
        asyncio.run(self._dkr_run('apt-get update', '/', deadline))
        asyncio.run(self._dkr_run('apt-get install -y python3', '/', deadline))

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

    def get_return_ip_addr(self):
        for iface in netifaces.interfaces():
            if iface == 'lo':
                continue
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET not in addrs:
                continue
            addrs = addrs[netifaces.AF_INET]
            if len(addrs) == 0:
                continue
            return addrs[0]['addr']
        return '0.0.0.0'

    async def _dkr_run(self, cmd, cwd, deadline, env=None):
        log.info('cmd %s', cmd)
        cmd = shlex.split(cmd)
        self.cntr.execute(cmd)
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

        deadline = time.time() + timeout
        if 'KRAKEN_LOGSTASH_ADDR' in os.environ:
            env = {'KRAKEN_LOGSTASH_ADDR': os.environ['KRAKEN_LOGSTASH_ADDR']}
        else:
            env = None
        try:
            await self._dkr_run(cmd, docker_cwd, deadline, env)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if self.proc_coord.result == {}:
                self.proc_coord.result = {'status': 'error', 'reason': 'timeout'}


def main():
    asyncio.run(run("ubuntu:19.04", "-h"))


if __name__ == '__main__':
    main()
