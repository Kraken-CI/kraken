import os
import io
import time
import asyncio
import tarfile
import logging


log = logging.getLogger(__name__)


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
        import docker
        self.client = docker.from_env()

        image = self.job['system']
        self.cntr = self.client.containers.run(image, 'sleep 10000', detach=True)
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
