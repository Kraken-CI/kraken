# Copyright 2020-2023 The Kraken Authors
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
import re
import sys
import time
import logging
import tempfile
import platform
import subprocess

import chardet

osname = platform.system()

log = logging.getLogger(__name__)


def _get_size(fname):
    with open(fname, "rb") as f:
        f.seek(0, 2)
        return f.tell()


def _trace_log_text2(log_text, output_handler, text, tracing, mask, out_prefix, trace_all):
    log_text = log_text.replace(b'\r\n', b'\n')

    if trace_all and not log_text.endswith(b'\n'):
        log_text += b'\n'

    lines = log_text.rsplit(b'\n', 1)
    if len(lines) == 1:
        # no new lines so nothing new to print
        log_text_left = lines[0]
    else:
        # some new line, so print all to last \n and the rest leave for the next iteration
        frag_to_print_now = lines[0]
        log_text_left = lines[1]

        enc = chardet.detect(frag_to_print_now)
        frag_to_print_now = frag_to_print_now.decode(enc.get('encoding', 'utf-8') or 'utf-8', 'ignore')

        if output_handler:
            output_handler(frag_to_print_now)
        elif text is not None:
            text.append(frag_to_print_now + '\n')
        if tracing:
            if mask:
                frag_to_print_now = frag_to_print_now.rstrip().replace(mask, '******')
            log.info("%s%s", out_prefix, frag_to_print_now)

    return log_text_left


def _trace_log_text(log_text, output_handler, text, tracing, mask, out_prefix, trace_all=False):
    text_left = b''
    # cut log to chunks to not get over log.info msg limit
    for i in range(0, len(log_text), 2048):
        chunk = log_text[i:i + 2048]

        # only the last chunk can have trace_all = True
        trace_all2 = False
        if trace_all and i + 2048 >= len(log_text):
            trace_all2 = True

        text_left = _trace_log_text2(text_left + chunk, output_handler, text, tracing, mask, out_prefix, trace_all2)
    return text_left


def _cleanup_process(p, cmd_trc):
    # once again at the end check if it completed, if not terminate or even kill the process
    if not p:
        return
    p.poll()
    if p.returncode is not None:
        return
    log.warning("terminating misbehaving cmd '%s'", cmd_trc)
    p.terminate()
    for _ in range(10):
        if p.poll():
            break
        time.sleep(0.1)
    if p.poll() is None:
        log.warning("killing bad cmd '%s'", cmd_trc)
        p.kill()
        for _ in range(10):
            if p.poll():
                break
            time.sleep(0.1)

def execute(cmd, timeout=60, cwd=None, env=None, output_handler=None, stderr=subprocess.STDOUT, tracing=True, raise_on_error=False,
            callback=None, cb_period=5, mask=None, out_prefix='output: ', ignore_output=False, executable=None):
    # pylint: disable=too-many-statements,too-many-branches,too-many-locals
    if cwd is None:
        cwd = os.getcwd()
    if mask:
        cmd_trc = cmd.replace(mask, '******')
    else:
        cmd_trc = cmd
    log.info("exec: '%s' in '%s'", cmd_trc, cwd)

    retcode = 0

    try:
        t_trace = t = time.time()
        t_cb = t - cb_period - 1  # force callback on first loop iteration
        t_end = t + timeout
        p = None

        fh, fname = tempfile.mkstemp(".txt", "exec_")

        p = subprocess.Popen(cmd,
                             shell=True,
                             executable=executable,
                             # TODO: this requires doing os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                             # like in local_run.py
                             # start_new_session=True,
                             env=env,
                             cwd=cwd,
                             stdout=fh,
                             stderr=stderr)
        log.info("exec: pid: %s", p.pid)

        # if 'clone' in cmd:
        #     from pudb.remote import set_trace
        #     set_trace(term_size=(208, 80))

        # read the output while process is working
        if ignore_output:
            text = None
        else:
            text = []
        out_size = 0
        completed = False
        out_fragment = b""
        t0_frag = time.time()
        with open(fname, 'rb') as f:
            while t < t_end and not completed:
                t = time.time()

                # call callback if time passed
                dt = t - t_cb
                if callback and dt > cb_period:
                    t_cb = t
                    if callback(True):
                        log.info("callback requested stopping cmd %s", cmd_trc)
                        break

                # handle output from subprocess
                s = _get_size(fname)
                ds = s - out_size
                out_size = s
                frag = b''
                if ds > 0:
                    frag = f.read(ds)
                if len(frag) == 0:
                    time.sleep(0.01)
                else:
                    out_fragment += frag
                    t1_frag = time.time()
                    # do not print too frequently, only every 128B or every 0.5s
                    if len(out_fragment) > 128 or t1_frag - t0_frag > 0.5:
                        out_fragment = _trace_log_text(out_fragment, output_handler, text, tracing, mask, out_prefix)

                # one trace for minute
                dt = t - t_trace
                if dt > 60:
                    t_trace = t
                    log.info("%s: %.2fsecs to terminate", cmd_trc, int(t_end - t))

                completed = p.poll() is not None

            # read the rest of output
            out_fragment += f.read()
            if len(out_fragment) > 0:
                _trace_log_text(out_fragment, output_handler, text, tracing, mask, out_prefix, trace_all=True)

    except Exception:
        log.exception('problem during executing cmd %s', cmd_trc)
        _cleanup_process(p, cmd_trc)
        raise
    finally:
        try:
            os.close(fh)
            os.unlink(fname)
        except Exception:
            log.exception('problem during closing exec log file %s', fname)

    # check if there was timeout exceeded
    if t > t_end:
        log.info("cmd %s exceeded timeout (%dsecs)", cmd_trc, timeout)
        retcode = 10000

    # once again at the end check if it completed, if not terminate or even kill the process
    _cleanup_process(p, cmd_trc)

    # not good, cannot kill process
    if p and p.poll() is None:
        log.error("cannot kill cmd '%s'", cmd_trc)

    if callback:
        callback(False)

    out = ''
    if output_handler is None and not ignore_output:
        out = "".join(text)

    if raise_on_error and p and p.returncode != 0:
        raise Exception("cmd failed: %s, exitcode: %d, out: %s" % (cmd_trc, p.returncode, out))

    # make sure that when there is error 'if retcode' turns True
    if retcode == 0:
        if not p or p.returncode is None:
            retcode = -1
        else:
            retcode = p.returncode

    if output_handler is None and not ignore_output:
        return retcode, out
    return retcode


def is_in_docker():
    if osname != 'Linux':
        return False

    try:
        with open('/proc/self/cgroup', 'r') as f:
            for line in f:
                fields = line.strip().split('/')
                if 'docker' in fields[1]:
                    return True
        with open('/proc/self/mountinfo', 'r') as f:
            for line in f:
                if re.search('/containers/[a-z0-9]{64}/hostname', line):
                    return True
    except Exception:
        log.warning('IGNORED', exc_info=sys.exc_info())
    return False


def is_in_lxc():
    if osname != 'Linux':
        return False

    try:
        with open('/proc/self/cgroup', 'r') as procfile:
            for line in procfile:
                fields = line.strip().split('/')
                if '.lxc' in fields[1]:
                    return True
    except Exception:
        log.warning('IGNORED', exc_info=sys.exc_info())
    return False


def get_times(deadline):
    now = time.time()
    t0 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    t1 = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deadline))
    time_left = deadline - now
    return t0, t1, time_left
