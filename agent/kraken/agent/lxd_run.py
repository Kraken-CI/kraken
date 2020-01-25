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


class LxdExecContext:
    def __init__(self, job):
        self.job = job

    def start(self, timeout):
        self.client = pylxd.Client()

        image = self.job['system']  # 'bionic/amd64'
        config = {'name': 'kktool', 'source': {'type': 'image',
                                               "mode": "pull",
                                               "server": "https://cloud-images.ubuntu.com/daily",
                                               "protocol": "simplestreams",
                                               'alias': image}}
        log.info('lxd container config: %s', config)
        self.cntr = self.client.containers.create(config, wait=True)
        self.cntr.start()
        log.info('lxd container %s', self.cntr.name)
        for _ in range(100):
            if self.cntr.status != 'Running':
                time.sleep(0.1)
                self.cntr.sync()
                log.info('container status %s', self.cntr.status)
        if self.cntr.status != 'Running':
            self.stop()
            raise Exception('cannot start container')

        with open('kktool', 'rb') as f:
            filedata = f.read()
        self.cntr.files.put('/root/kktool', filedata)

        deadline = time.time() + timeout
        asyncio.run(self._lxd_run('chmod a+x kktool', '.', deadline))
        asyncio.run(self._lxd_run('apt-get update', '/', deadline))
        asyncio.run(self._lxd_run('apt-get install -y python3', '/', deadline))

    def stop(self):
        try:
            self.cntr.stop()
        except:
            # TODO: add some ignore trace here
            pass
        try:
            self.cntr.delete()
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

    def _stdout_handler(self, chunk):
        log.info(chunk.decode().rstrip())

    async def _lxd_run(self, cmd, cwd, deadline, env=None):
        log.info('cmd %s', cmd)
        cmd = shlex.split(cmd)
        result = self.cntr.execute(cmd, environment=env, stdout_handler=self._stdout_handler, stderr_handler=self._stdout_handler)
        log.info('EXIT: %s', result.exit_code)

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout):
        lxd_cwd = '/root'

        # upload steop file
        dest_step_file_path = os.path.join(lxd_cwd, os.path.basename(step_file_path))
        with open(step_file_path, 'rb') as f:
            filedata = f.read()
        self.cntr.files.put(dest_step_file_path, filedata)

        mod = tool_path.split()[-1]
        cmd = "%s/kktool -m %s -r %s -s %s %s" % (lxd_cwd, mod, return_addr, dest_step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, lxd_cwd, timeout)

        deadline = time.time() + timeout
        if 'KRAKEN_LOGSTASH_ADDR' in os.environ:
            env = {'KRAKEN_LOGSTASH_ADDR': os.environ['KRAKEN_LOGSTASH_ADDR']}
        else:
            env = None
        try:
            await self._lxd_run(cmd, lxd_cwd, deadline, env)
        except Timeout:
            # TODO: it should be better handled but needs testing
            if self.proc_coord.result == {}:
                self.proc_coord.result = {'status': 'error', 'reason': 'timeout'}


def main():
    asyncio.run(run("ubuntu:19.04", "-h"))


if __name__ == '__main__':
    main()
