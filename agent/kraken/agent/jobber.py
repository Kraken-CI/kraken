import os
import sys
import json
import logging
import pkgutil
import asyncio
import datetime
import traceback
import socketserver
import multiprocessing

from . import config
from . import tool
from . import utils


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
        self.start_time = None
        self.end_time = None


async def _async_pump_output(proc_coord, stream):
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


async def _async_monitor_proc(proc_coord, proc, timeout):
    end_time = proc_coord.start_time + datetime.timedelta(seconds=timeout)
    while True:
        if proc.returncode is not None:
            break

        now = datetime.datetime.now()
        if now < end_time:
            await asyncio.sleep(1)
            continue

        log.warn("cmd %s exceeded timeout (%dsecs), terminating", cmd, timeout)
        proc.terminate()
        for _ in range(10):
            if proc.returncode is not None:
                break
            await asyncio.sleep(0.1)
        if proc.returncode is None:
            log.warn("killing bad cmd '%s'", cmd)
            proc.kill()
            for _ in range(10):
                if proc.returncode is not None:
                    break
                await asyncio.sleep(0.1)
        break



async def _async_subprocess(proc_coord, cmd, cwd, timeout):
    log.info("exec: '%s' in '%s'", cmd, cwd)

#    with tempfile.NamedTemporaryFile(suffix=".txt", prefix="exec_") as fh:
#        fname = fh.name
#        proc_coord.output_file = fname
#        pump = asyncio.create_task(_async_pump_output(proc_coord, fname))

    proc_coord.start_time = datetime.datetime.now()

    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        limit=1024 * 128,  # 128 KiB
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)

    await _async_pump_output(proc_coord, proc.stdout)

    done, pending = await asyncio.wait([proc.wait(), _async_monitor_proc(proc_coord, proc, timeout)],
                                       timeout=timeout * 1.1)
    #log.info('done %s', done)
    #log.info('pending %s', pending)
    proc_coord.end_time = datetime.datetime.now()
    proc_coord.proc_retcode = proc.returncode

#        proc_coord.output_file = None



class RequestHandler():
    def __init__(self, proc_coord):
        self.proc_coord = proc_coord

    async def _async_handle_request(self, reader, writer):
        addr = writer.get_extra_info('peername')
        while True:
            #data = await reader.read(8192)
            data = await reader.readline()
            if not data:
                break
            try:
                data = data.decode()
                #log.info("received %s from %s", data, addr)
                data = json.loads(data)
            except:
                log.exception('problem with decoding data %s from %s', data, addr)
                return

            self.proc_coord.result = data

            if self.proc_coord.command == 'run_tests':
                # report partial results
                srv = self.proc_coord.kk_srv
                # TODO: check if result is not send twice: here and at the end of process
                srv.report_step_result(self.proc_coord.job_id,
                                       self.proc_coord.idx,
                                       self.proc_coord.result)
                self.proc_coord.result = {'status': 'in-progress'}


async def _async_tcp_server(proc_coord, server):
    async with server:
        await server.serve_forever()


async def _async_exec_tool(proc_coord, tool_path, command, cwd, timeout, step_file_path):
    handler = RequestHandler(proc_coord)
    server = await asyncio.start_server(handler._async_handle_request, '0.0.0.0', 0, limit=1024 * 1280)
    addr = server.sockets[0].getsockname()
    return_addr = "%s:%s" % addr

    cmd = "%s -r %s -s %s %s" % (tool_path, return_addr, step_file_path, command)

    subprocess_task = asyncio.create_task(_async_subprocess(proc_coord, cmd, cwd, timeout))
    tcp_server_task = asyncio.create_task(_async_tcp_server(proc_coord, server))
    done, pending = await asyncio.wait([subprocess_task, tcp_server_task],
                                       return_when=asyncio.FIRST_COMPLETED)
    if tcp_server_task not in done:
        tcp_server_task.cancel()
        try:
            await tcp_server_task
        except asyncio.CancelledError:
            pass

def _exec_tool(kk_srv, tool_path, command, cwd, timeout, step_file_path, job_id, idx):
    if tool_path.endswith('.py'):
        tool_path = "%s %s" % (sys.executable, tool_path)

    proc_coord = ProcCoord(kk_srv, command, job_id, idx)
    asyncio.run(_async_exec_tool(proc_coord, tool_path, command, cwd, timeout, step_file_path))
    return proc_coord.result


def _write_step_file(job_dir, step, idx):
    step_data = json.dumps(step)
    step_file_path = os.path.join(job_dir, 'step_%d.json' % idx)
    with open(step_file_path, 'w') as f:
        f.write(step_data)
    return step_file_path


def _run_step(srv, job_dir, job_id, idx, step, tools):
    tool_name = step['tool']
    log.info('step %s', str(step)[:200])
    if tool_name not in tools:
        raise Exception('No such Kraken tool: %s' % tool_name)
    tool_path = tools[tool_name]

    step_file_path = _write_step_file(job_dir, step, idx)

    result = _exec_tool(srv, tool_path, 'get_commands', job_dir, 10, step_file_path, job_id, idx)
    log.info('result for get_commands: %s', result)
    if not isinstance(result, dict) or 'commands' not in result:
        raise Exception('bad result received from tool: %s' % result)
    available_commands = result['commands']

    if 'run' not in available_commands and 'run_tests' not in available_commands:
        raise Exception('missing run and run_tests in available commands: %s' % available_commands)

    if 'collect_tests' in available_commands and ('tests' not in step or step['tests'] is None or len(step['tests']) == 0):
        # collect tests from tool to execute
        result = _exec_tool(srv, tool_path, 'collect_tests', job_dir, 10, step_file_path, job_id, idx)
        log.info('result for collect_tests: %s', str(result)[:200])

        # check result
        if not isinstance(result, dict):
            raise Exception('bad result received from tool: %s' % result)

        # if command not succeeded
        if result['status'] != 'done':
            srv.report_step_result(job_id, idx, result)
            return result

        # check result
        if 'tests' not in result:
            raise Exception('bad result received from tool: %s' % result)

        # if no test returned then report error
        if len(result['tests']) == 0:
            result = {'status': 'error', 'reason': 'no-tests'}
            srv.report_step_result(job_id, idx, result)
            return result

        # if there are tests then send them for dispatching to server
        response = srv.dispatch_tests(job_id, idx, result['tests'])
        step['tests'] = response['tests']
        _write_step_file(job_dir, step, idx)

    if 'run_tests' in available_commands:
        result = _exec_tool(srv, tool_path, 'run_tests', job_dir, 60, step_file_path, job_id, idx)
        log.info('result for run_tests: %s', str(result)[:200])
        srv.report_step_result(job_id, idx, result)

    if 'run' in available_commands:
        result = _exec_tool(srv, tool_path, 'run', job_dir, 60, step_file_path, job_id, idx)
        log.info('result for run: %s', result)
        srv.report_step_result(job_id, idx, result)

    return result


def run(srv, job):
    tools = _load_tools_list()

    data_dir = config.get('data_dir')
    job_dir = os.path.join(data_dir, 'jobs', str(job['id']))
    if not os.path.exists(job_dir):
        os.makedirs(job_dir)

    log.info('started job in %s', job_dir)

    last_status = None
    for idx, step in enumerate(job['steps']):
        step['job_id'] = job['id']
        log.set_ctx(step=idx)
        if step['status'] == 2:
            continue
        try:
            result = _run_step(srv, job_dir, job['id'], idx, step, tools)
            last_status = result['status']
        except KeyboardInterrupt:
            raise
        except:
            log.exception('step interrupted by exception')
            exc = traceback.format_exc()
            srv.report_step_result(job['id'], idx, {'status': 'error', 'reason': 'exception', 'msg': exc})
            last_status = 'error'

        if last_status == 'error':
            break

    log.info('completed job %s with status %s', job['id'], last_status)


def test():
    config.set_config({"data_dir": "/tmp", "tools_dirs": "/tmp"})
    with open(sys.argv[1]) as f:
        job = json.loads(f.read())
    run(None, job)


if __name__ == '__main__':
    test()
