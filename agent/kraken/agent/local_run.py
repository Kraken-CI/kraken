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

import asyncio
import logging
import datetime

from . import sysutils

log = logging.getLogger(__name__)


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
            log.info('adr: %s', ip_addr)
            if iface == 'lo':
                continue
            return ip_addr
        return '0.0.0.0'

    async def async_run(self, proc_coord, tool_path, return_addr, step_file_path, command, cwd, timeout, user):
        cmd = "%s -r %s -s %s %s" % (tool_path, return_addr, step_file_path, command)
        log.info("exec: '%s' in '%s', timeout %ss", cmd, cwd, timeout)

        self.proc_coord = proc_coord
        self.cmd = cmd

        self.start_time = datetime.datetime.now()

        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            limit=1024 * 128,  # 128 KiB
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)

        await self._async_pump_output(proc.stdout)

        await asyncio.wait([proc.wait(), self._async_monitor_proc(proc, timeout * 0.95)],
                           timeout=timeout)
        #log.info('done %s', done)
        #log.info('pending %s', pending)
        #proc_coord.proc_retcode = proc.returncode

    async def _async_pump_output(self, stream):
        while True:
            try:
                line = await stream.readline()
            except ValueError:
                log.exception('IGNORED')
                continue
            if line:
                line = line.decode().rstrip()
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
