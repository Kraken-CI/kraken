# Copyright 2020-2022 The Kraken Authors
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
import signal
import asyncio
import logging
import datetime
import zipfile

from . import consts
from . import config
from . import sysutils
from . import miniobase

log = logging.getLogger(__name__)


def detect_capabilities():
    return {}


class LocalExecContext:
    def __init__(self, job):
        self.job = job

        self.proc_coord = None
        self.cmd = None
        self.start_time = None

    def start(self, timeout):
        pass

    def stop(self):
        pass

    def get_return_ip_addr(self):  # pylint: disable=no-self-use
        for iface, ip_addr in sysutils.get_ifaces():
            if iface == 'lo':
                continue
            return ip_addr
        return '0.0.0.0'

    async def async_run(self, proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user):   # pylint: disable=unused-argument
        pypath, mod = tool_path
        cmd = "%s/kktool -m %s -r %s -s %s %s" % (consts.AGENT_DIR, mod, return_addr, step_file_path, command)

        if pypath and pypath.startswith('minio:'):
            m_bucket, m_path, _ = pypath[6:].split('/')
            data_dir = config.get('data_dir')
            tool_dir = os.path.join(data_dir, 'tools', m_bucket, m_path)
            tool_zip = miniobase.download_tool(step, pypath)
            with zipfile.ZipFile(tool_zip) as zf:
                zf.extractall(tool_dir)
            pypath = tool_dir
            os.unlink(tool_zip)

        if pypath:
            pypath += ':%s/vendor' % pypath
            cmd = 'PYTHONPATH=%s %s' % (pypath, cmd)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, cwd, timeout)

        # setup log context
        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)
        log_ctx = dict(job=step['job_id'], step=step['index'], tool=step['tool'])

        self.proc_coord = proc_coord
        self.cmd = cmd

        self.start_time = datetime.datetime.now()

        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            limit=1024 * 128,  # 128 KiB
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True)

        try:
            await self._async_pump_output(proc.stdout, log_ctx)

            if timeout:
                await asyncio.wait([proc.wait(), self._async_monitor_proc(proc, timeout * 0.95)],
                                   timeout=timeout)
            else:
                await proc.wait()
        except asyncio.CancelledError:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1)
            await asyncio.wait_for(proc.wait(), timeout=1)
            if proc.returncode is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                time.sleep(1)
            await proc.wait()
            raise
        #log.info('done %s', done)
        #log.info('pending %s', pending)
        #proc_coord.proc_retcode = proc.returncode

    async def _async_pump_output(self, stream, log_ctx):
        while True:
            try:
                line = await stream.readline()
            except ValueError:
                log.exception('IGNORED')
                continue
            if line:
                line = line.decode().rstrip()
                log.set_ctx(**log_ctx)
                log.info(line)
                log.reset_ctx()
            else:
                break

    async def _async_monitor_proc(self, proc, timeout):
        end_time = self.start_time + datetime.timedelta(seconds=timeout)
        while True:
            if proc.returncode is not None:
                break

            now = datetime.datetime.now()
            if now < end_time:
                await asyncio.sleep(1)
                continue

            log.warning("cmd %s exceeded timeout (%dsecs), terminating", self.cmd, timeout)
            proc.terminate()
            for _ in range(10):
                if proc.returncode is not None:
                    break
                await asyncio.sleep(0.1)
            if proc.returncode is None:
                log.warning("killing bad cmd '%s'", self.cmd)
                proc.kill()
                for _ in range(10):
                    if proc.returncode is not None:
                        break
                    await asyncio.sleep(0.1)

            # TODO: it should be better handled but needs testing
            if self.proc_coord.result == {}:
                self.proc_coord.result = {'status': 'error', 'reason': 'job-timeout'}
            break
