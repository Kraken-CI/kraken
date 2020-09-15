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

import os
import time
import subprocess
import logging
import tempfile

log = logging.getLogger(__name__)


def _get_size(fname):
    with open(fname, "rb") as f:
        f.seek(0, 2)
        return f.tell()


def execute(cmd, timeout=60, cwd=None, env=None, output_handler=None, stderr=subprocess.STDOUT, tracing=True, raise_on_error=False,
            callback=None, cb_period=5, mask=None, out_prefix='output: '):
    # pylint: disable=too-many-statements,too-many-branches,too-many-locals
    if cwd is None:
        cwd = os.getcwd()
    if mask:
        cmd_trc = cmd.replace(mask, '******')
    else:
        cmd_trc = cmd
    log.info("exec: '%s' in '%s'", cmd_trc, cwd)

    with tempfile.NamedTemporaryFile(suffix=".txt", prefix="exec_") as fh:
        fname = fh.name

        p = subprocess.Popen(cmd,
                             shell=True,
                             universal_newlines=True,
                             start_new_session=True,
                             env=env,
                             cwd=cwd,
                             stdout=fh,
                             stderr=stderr)

        # if 'clone' in cmd:
        #     from pudb.remote import set_trace
        #     set_trace(term_size=(208, 80))

        # read the output while process is working
        t_trace = t = time.time()
        t_cb = t - cb_period - 1  # force callback on first loop iteration
        t_end = t + timeout
        text = []
        out_size = 0
        completed = False
        with open(fname) as f:
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
                out_fragment = ""
                s = _get_size(fname)
                ds = s - out_size
                out_size = s
                if ds > 0:
                    out_fragment = f.read(ds)
                if len(out_fragment) > 0:
                    if output_handler:
                        output_handler(out_fragment)
                    else:
                        text.append(out_fragment)
                    if tracing:
                        if mask:
                            out_fragment = out_fragment.rstrip().replace(mask, '******')
                        log.info("%s%s", out_prefix, out_fragment.rstrip())

                # one trace for minute
                dt = t - t_trace
                if dt > 60:
                    t_trace = t
                    log.info("%s: %.2fsecs to terminate", cmd_trc, int(t_end - t))

                completed = p.poll() is not None

            # read the rest of output
            out_fragment = f.read()
            if len(out_fragment) > 0:
                if output_handler:
                    output_handler(out_fragment)
                else:
                    text.append(out_fragment)
                if tracing:
                    if mask:
                        out_fragment = out_fragment.rstrip().replace(mask, '******')
                    log.info("%s%s", out_prefix, out_fragment.rstrip())

    # check if there was timeout exceeded
    if t > t_end:
        log.info("cmd %s exceeded timeout (%dsecs)", cmd_trc, timeout)

    # once again at the end check if it completed, if not terminate or even kill the process
    p.poll()
    if p.returncode is None:
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

    # not good, cannot kill process
    if p.poll() is None:
        log.error("cannot kill cmd '%s'", cmd_trc)

    if callback:
        callback(False)

    if output_handler is None:
        out = "".join(text)

    if raise_on_error and p.returncode != 0:
        raise Exception("cmd failed: %s, exitcode: %d, out: %s" % (cmd_trc, p.returncode, out))

    # make sure that when there is error 'if retcode' turns True
    if p.returncode is None:
        retcode = -1
    else:
        retcode = p.returncode

    if output_handler is None:
        return retcode, out
    return retcode
