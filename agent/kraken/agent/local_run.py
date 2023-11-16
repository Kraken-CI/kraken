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
import sys
import json
import time
import signal
import asyncio
import logging
import zipfile
import platform
import datetime

from . import sysutils
from . import miniobase

osname = platform.system()


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

    async def _async_run_exc(self, proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        pypath, mod = tool_path

        executable = os.path.join(sysutils.get_agent_dir(), 'kktool')
        if osname == 'Windows':
            executable = 'python.exe ' + executable

        cmd = "%s -m %s -r %s -s %s %s" % (executable, mod, return_addr, step_file_path, command)

        if pypath and pypath.startswith('minio:'):
            tool_zip, _, _ = miniobase.download_tool(step, pypath)
            tool_dir = os.path.dirname(tool_zip)
            with zipfile.ZipFile(tool_zip) as zf:
                zf.extractall(tool_dir)
            pypath = tool_dir

        if pypath:
            pypath += ':%s/vendor' % pypath
            cmd = 'PYTHONPATH=%s %s' % (pypath, cmd)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, cwd, timeout)

        # setup log context
        with open(step_file_path) as f:
            data = f.read()
        step = json.loads(data)

        self.proc_coord = proc_coord
        self.cmd = cmd

        self.start_time = datetime.datetime.now()

        if 'branch_env' in step and step['branch_env']:
            env = os.environ.copy()
            env.update(step['branch_env'])
        else:
            env = None

        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            limit=1024 * 128,  # 128 KiB
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            env=env)

        try:
            await self._async_pump_output(proc.stdout)

            if timeout:
                proc_task = asyncio.create_task(proc.wait())
                monitor_task = asyncio.create_task(self._async_monitor_proc(proc, timeout * 0.95))
                await asyncio.wait([proc_task, monitor_task], timeout=timeout)
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
        # log.info('async run completed, %s', command)
        #proc_coord.proc_retcode = proc.returncode

    async def async_run(self, proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user):  # pylint: disable=unused-argument
        try:
            await self._async_run_exc(proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user)
        except Exception:
            log.exception('passing up')
            raise

    async def _async_pump_output(self, stream):
        while True:
            try:
                line = await stream.readline()
            except ValueError:
                log.warning('IGNORED', exc_info=sys.exc_info())
                continue
            if line:
                line = line.decode(errors="ignore").rstrip()
                log.info(line)
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
