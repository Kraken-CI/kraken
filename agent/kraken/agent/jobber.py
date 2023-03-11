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
import logging
import pkgutil
import asyncio
import traceback
# import socketserver
import threading
import pkg_resources

from . import config
from . import local_run
from . import docker_run
from . import lxd_run
from . import utils
from . import consts

log = logging.getLogger(__name__)


def _load_tools_list():
    tools = {}
    tools_dirs = [os.getcwd()]
    cfg_tools_dir = config.get('tools_dirs')
    if cfg_tools_dir:
        tools_dirs.extend(cfg_tools_dir.split(','))
    mods = pkgutil.iter_modules(tools_dirs)
    for mod in mods:
        finder, name, _ = mod
        if not name.startswith('kraken_'):
            continue
        n = name.replace('kraken_', '')
        spec = finder.find_spec(name)
        tools[n] = spec.origin

    for entry_point in pkg_resources.iter_entry_points('kraken.tools'):
        entry_point.load()
        # log.info("TOOL %s: %s", entry_point.name, entry_point.module_name)
        tools[entry_point.name] = (None, entry_point.module_name)

    return tools


# class MyTCPHandler(socketserver.BaseRequestHandler):
#     def handle(self):
#         log.info('MyTCPHandler::handle')
#         # self.request is the TCP socket connected to the client
#         data = self.request.recv(8192).strip()
#         log.info("{} wrote:".format(self.client_address[0]))
#         log.info(data)

#         if self.server.kk_command == 'get-commands':
#             self.server.kk_result = json.loads(data)


# class MyTCPServer(socketserver.TCPServer):
#     def __init__(self, command):
#         self.timeout = 2
#         self.kk_command = command
#         self.kk_result = None
#         socketserver.TCPServer.__init__(self, ('', 0), MyTCPHandler)

#     def my_handle_request(self, running):
#         log.info('my_handle_request %s', running)
#         if running:
#             self.handle_request()


# def _exec_tool(kk_srv, tool_path, command, cwd, step_file_path):

#     with MyTCPServer(command) as server:
#         return_addr = "%s:%s" % server.server_address

#         if tool_path.endswith('.py'):
#             tool_path = "%s %s" % (sys.executable, tool_path)

#         cmd = "%s -r %s -s %s %s" % (tool_path, return_addr, step_file_path, command)
#         oh = None
#         ret, _ = utils.execute(cmd,
#                                cwd=cwd,
#                                output_handler=oh,
#                                callback=server.my_handle_request)

#         if ret == 0:
#             if server.kk_result is None:
#                 raise Exception("no result from tool")
#             else:
#                 result = server.kk_result
#         else:
#             result = {'status': 'error', 'reason': 'retcode', 'retcode': ret}
#             if server.kk_result:
#                 result = server.kk_result.update(result)

#         return result

class ProcCoord():
    def __init__(self, kk_srv, command, job_id, idx):
        self.kk_srv = kk_srv
        self.command = command
        self.job_id = job_id
        self.idx = idx

        self.result = {}
        self.is_canceled = False

        self.subprocess_task = None

        self.start_time = time.time()

    def cancel(self):
        self.is_canceled = True
        if self.subprocess_task:
            self.subprocess_task.cancel()


class RequestHandler():
    def __init__(self, proc_coord):
        self.proc_coord = proc_coord

    async def async_handle_request(self, reader, writer):
        addr = writer.get_extra_info('peername')
        while True:
            # data = await reader.read(8192)
            data = await reader.readline()
            if not data:
                break
            try:
                data = data.decode()
                #log.info("received %s from %s", data, addr)
                data = json.loads(data)
            except Exception:
                log.exception('problem with decoding data %s from %s', data, addr)
                return

            data['duration'] = round(time.time() - self.proc_coord.start_time + 0.5)
            self.proc_coord.result = data

            if self.proc_coord.command in ['run_tests', 'run_analysis', 'run_artifacts', 'run_data']:
                # report partial results
                srv = self.proc_coord.kk_srv
                rsp = srv.report_step_result(self.proc_coord.job_id,
                                             self.proc_coord.idx,
                                             self.proc_coord.result)
                if rsp.get('cancel', False):
                    self.proc_coord.cancel()


async def _async_tcp_server(server):
    try:
        await server.serve_forever()
    finally:
        server.close()
        await server.wait_closed()


async def _send_keep_alive_to_server(proc_coord):
    srv = proc_coord.kk_srv
    while True:
        await asyncio.sleep(10)
        try:
            rsp = srv.keep_alive(proc_coord.job_id)
        except Exception:
            log.exception('IGNORED EXCEPTION')
            continue
        if rsp.get('cancel', False):
            proc_coord.cancel()


async def _wait_for_cancel(cancel_event):
    while True:
        await asyncio.sleep(1)
        if cancel_event.is_set():
            break


async def _async_exec_tool(exec_ctx, proc_coord, tool_path, command, cwd, timeout, user, step, step_file_path, cancel_event=None):
    # prepare internal http server for receiving messages from tool subprocess
    addr = exec_ctx.get_return_ip_addr()
    # log.info('return ip addr %s', addr)
    handler = RequestHandler(proc_coord)
    server = await asyncio.start_server(handler.async_handle_request, addr, 0, limit=1024 * 1280)
    addr = server.sockets[0].getsockname()
    return_addr = "%s:%s" % addr
    # log.info('return_addr %s', return_addr)

    # async task with tool subprocess
    subprocess_task = asyncio.ensure_future(exec_ctx.async_run(
        proc_coord, tool_path, return_addr, step, step_file_path, command, cwd, timeout, user))
    proc_coord.subprocess_task = subprocess_task

    # async task with internal http server
    tcp_server_task = asyncio.ensure_future(_async_tcp_server(server))

    # async task for sending keep alive messages to kraken server
    keep_alive_task = asyncio.ensure_future(_send_keep_alive_to_server(proc_coord))

    tasks = [subprocess_task, tcp_server_task, keep_alive_task]

    # waiting for cancel task if needed
    if cancel_event:
        cancel_task = asyncio.ensure_future(_wait_for_cancel(cancel_event))
        tasks.append(cancel_task)
    else:
        cancel_task = None

    # wait for any task to complete
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for t in done:
        ex = None
        try:
            ex = t.exception()
        except Exception as e:
            ex = e
        if ex:
            if not proc_coord.result:
                proc_coord.result = {'status': 'error', 'reason': 'exception', 'msg': str(ex)}

    # stop internal http server if not stopped yet
    if tcp_server_task not in done:
        tcp_server_task.cancel()
        try:
            await tcp_server_task
        except asyncio.CancelledError:
            pass

    if cancel_task and cancel_task in done:
        subprocess_task.cancel()
        try:
            await subprocess_task
        except asyncio.CancelledError:
            pass


def _exec_tool_inner(kk_srv, exec_ctx, tool_path, command, cwd, timeout, user, step, step_file_path, job_id, idx, cancel_event=None):
    # TODO is it still needed
    # if tool_path.endswith('.py'):
    #     tool_path = "%s %s" % (sys.executable, tool_path)

    proc_coord = ProcCoord(kk_srv, command, job_id, idx)
    f = _async_exec_tool(exec_ctx, proc_coord, tool_path, command, cwd, timeout, user, step, step_file_path, cancel_event)
    try:
        if hasattr(asyncio, 'run'):
            asyncio.run(f)  # this is available since Python 3.7
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(f)
            loop.close()
    except asyncio.CancelledError:
        pass
    return proc_coord.result, proc_coord.is_canceled


def _exec_tool(kk_srv, exec_ctx, tool_path, command, cwd, timeout, user, step, step_file_path, job_id, idx, background=False):
    if background:
        cancel_event = threading.Event()
        timeout = 60 * 60 * 24 * 3  # bg steps should have infinite timeout but let's set it to 3 days
        th = threading.Thread(target=_exec_tool_inner, args=(kk_srv, exec_ctx, tool_path, command, cwd, timeout,
                                                             user, step, step_file_path, job_id, idx, cancel_event))
        th.start()
        return (th, cancel_event), None

    result, cancel = _exec_tool_inner(kk_srv, exec_ctx, tool_path, command, cwd, timeout, user, step, step_file_path, job_id, idx)
    return result, cancel


def _write_step_file(job_dir, step, idx):
    step_data = json.dumps(step)
    step_file_path = os.path.join(job_dir, 'step_%d.json' % idx)
    with open(step_file_path, 'w') as f:
        f.write(step_data)
    return step_file_path


def _get_tool(tools, name, step):
    if name in tools:
        return tools[name]

    return (step['tool_location'], step['tool_entry'])

    #raise Exception('Cannot find Kraken tool: %s' % name)


def _run_step(srv, exec_ctx, job_dir, job_id, idx, step, tools, deadline):
    tool_name = step['tool']
    t0, t1, timeout = utils.get_times(deadline)
    step_str = '<id:%d tool:%s>' % (step['id'], step['tool'])
    log.info('step %d. %s, now %s, deadline %s, time: %ds', idx, step_str, t0, t1, timeout)
    tool_path = _get_tool(tools, tool_name, step)

    user = step.get('user', '')

    rsp = srv.report_step_result(job_id, idx, {'status': 'in-progress'})

    step_file_path = _write_step_file(job_dir, step, idx)

    cancel = False
    bg_step = None

    result, cancel = _exec_tool(srv, exec_ctx, tool_path, 'get_commands', job_dir, 20, user, step, step_file_path, job_id, idx)
    log.info('result for get_commands: %s', result)
    # check result
    if not isinstance(result, dict) or 'status' not in result:
        raise Exception('bad result received from tool: %s' % result)
    # if command not succeeded
    if result['status'] != 'done':
        rsp = srv.report_step_result(job_id, idx, result)
        return result['status'], rsp.get('cancel', False), bg_step
    # check if commands in result
    if 'commands' not in result:
        raise Exception('bad result received from tool: %s' % result)
    available_commands = result['commands']

    if ('run' not in available_commands and
        'run_tests' not in available_commands and
        'run_analysis' not in available_commands and
        'run_artifacts' not in available_commands and
        'run_data' not in available_commands):
        raise Exception('missing run and run_tests in available commands: %s' % available_commands)

    if 'collect_tests' in available_commands and ('tests' not in step or step['tests'] is None or len(step['tests']) == 0):
        # collect tests from tool to execute
        result, cancel = _exec_tool(srv, exec_ctx, tool_path, 'collect_tests', job_dir, 20, user, step, step_file_path, job_id, idx)
        log.info('result for collect_tests: %s', str(result)[:200])
        if cancel:
            log.info('canceling job')
            return 'cancel', cancel, bg_step

        # check result
        if not isinstance(result, dict):
            raise Exception('bad result received from tool: %s' % result)

        # if command not succeeded
        if result['status'] != 'done':
            rsp = srv.report_step_result(job_id, idx, result)
            return result['status'], rsp.get('cancel', False), bg_step

        # check result
        if 'tests' not in result:
            raise Exception('bad result received from tool: %s' % result)

        # if no test returned then report error
        if len(result['tests']) == 0:
            result = {'status': 'error', 'reason': 'no-tests'}
            rsp = srv.report_step_result(job_id, idx, result)
            return result['status'], rsp.get('cancel', False), bg_step

        # if there are tests then send them for dispatching to server
        response = srv.dispatch_tests(job_id, idx, result['tests'])
        step['tests'] = response['tests']
        _write_step_file(job_dir, step, idx)

    for run_cmd in ['run_tests', 'run_analysis', 'run_artifacts', 'run_data']:
        if run_cmd in available_commands:
            timeout = deadline - time.time()
            if timeout <= 0:
                log.info('timout expired %s', deadline)
                result = {'status': 'error', 'reason': 'job-timeout'}
                srv.report_step_result(job_id, idx, result)
                return result['status'], cancel, bg_step
            result, cancel = _exec_tool(srv, exec_ctx, tool_path, run_cmd, job_dir, timeout, user, step, step_file_path, job_id, idx)
            log.info('result for %s: %s', run_cmd, str(result)[:200])
            # do not srv.report_step_result, it was already done in RequestHandler.async_handle_request
            if cancel:
                log.info('canceling job')
                return 'cancel', cancel, bg_step

    if 'run' in available_commands:
        timeout = deadline - time.time()
        if timeout <= 0:
            log.info('timout expired %s', deadline)
            result = {'status': 'error', 'reason': 'job-timeout'}
            srv.report_step_result(job_id, idx, result)
            return result['status'], cancel, bg_step

        attempts = step.get('attempts', 1)
        sleep_time_after_attempt = step.get('sleep_time_after_attempt', 0)
        background = step.get('background', False)
        for n in range(attempts):
            result, cancel = _exec_tool(srv, exec_ctx, tool_path, 'run', job_dir, timeout, user, step, step_file_path, job_id, idx, background=background)
            if background:
                bg_step = result
                result = {'status': 'done'}
                break

            if cancel:
                log.info('canceling job')
                return 'cancel', cancel, bg_step

            if 'status' not in result:
                msg = 'missing status in result: %s' % str(result)
                log.error(msg)
                if not result:
                    result = {}
                result['status'] = 'error'
                result['reason'] = msg

            if result['status'] == 'done':
                break
            retry_info = 'no more retries' if n + 1 == attempts else ('retrying after %ds' % sleep_time_after_attempt)
            log.info('command failed, it was attempt %d/%d, %s', n + 1, attempts, retry_info)
            if sleep_time_after_attempt > 0:
                time.sleep(sleep_time_after_attempt)

        log.info('result for run: %s', result)
        rsp = srv.report_step_result(job_id, idx, result)
        cancel = rsp.get('cancel', False)
        if cancel:
            log.info('canceling job')

    return result['status'], cancel, bg_step


def _create_exec_context(job):
    if job['executor'] == 'docker':
        ctx = docker_run.DockerExecContext(job)
    elif job['executor'] == 'lxd':
        ctx = lxd_run.LxdExecContext(job)
    else:
        ctx = local_run.LocalExecContext(job)
    return ctx


def run(srv, job):
    tools = _load_tools_list()

    data_dir = config.get('data_dir')
    job_dir = os.path.join(data_dir, 'jobs', str(job['id']))
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)

    log.info('started job in %s', job_dir)

    exec_ctx = _create_exec_context(job)
    timeout = job['deadline'] - time.time()
    result = exec_ctx.start(timeout)
    if result is not None:
        srv.report_step_result(job['id'], 0, result)
        log.info('completed job %s with status %s', job['id'], result['status'])
        return

    try:
        bg_steps = []
        last_status = None
        for idx, step in enumerate(job['steps']):
            if step['status'] == consts.STEP_STATUS_DONE:
                continue
            log.set_ctx(step=idx)

            step['job_id'] = job['id']
            step['branch_id'] = job['branch_id']
            step['flow_kind'] = job['flow_kind']
            step['flow_id'] = job['flow_id']
            step['run_id'] = job['run_id']
            if 'trigger_data' in job:
                step['trigger_data'] = job['trigger_data']

            try:
                last_status, cancel, bg_step = _run_step(srv, exec_ctx, job_dir, job['id'], idx, step, tools, job['deadline'])
            except Exception:
                log.exception('step interrupted by exception')
                exc = traceback.format_exc()
                srv.report_step_result(job['id'], idx, {'status': 'error', 'reason': 'exception', 'msg': exc})
                last_status = 'error'
                bg_step = None

            if bg_step:
                bg_steps.append(bg_step)

            if last_status == 'error':
                break
            if cancel:
                log.info('received job cancel')
                break

        for bg_step in bg_steps:
            thread, cancel_event = bg_step
            cancel_event.set()
            thread.join()

    finally:
        exec_ctx.stop()

    log.info('completed job %s with status %s', job['id'], last_status)


def test():
    config.set_config({"data_dir": "/tmp", "tools_dirs": "/tmp"})
    with open(sys.argv[1]) as f:
        job = json.loads(f.read())
    run(None, job)


if __name__ == '__main__':
    test()
