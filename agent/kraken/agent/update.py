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
import sys
import shutil
import logging
import platform
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from . import config
from . import consts
from . import sysutils


osname = platform.system()


log = logging.getLogger(__name__)


def get_blob(dest_dir, name):
    srv_url = config.get('server')
    url = urljoin(srv_url, 'install/' + name)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as f:
        data = f.read()
    path = dest_dir / ('kk' + name)
    with path.open('wb') as f:
        f.write(data)
    path.chmod(0o777)
    return path


def get_blobs(dest_dir):
    a = get_blob(dest_dir, 'agent')
    t = get_blob(dest_dir, 'tool')
    return a, t


def get_agent_dir():
    if osname == 'Windows':
        return consts.AGENT_DIR_WIN
    else:
        return consts.AGENT_DIR


def get_dest_dir(version):
    dest_dir = Path(get_agent_dir()) / version
    return dest_dir


def prepare_dest_dir(version):
    dest_dir = get_dest_dir(version)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    return dest_dir


def make_links_to_new_binaries(dest_dir):
    agent_dir = get_agent_dir()

    for f in ['kkagent', 'kktool']:
        src_path = os.path.join(dest_dir, f)
        dest_path = os.path.join(agent_dir, f)

        if os.path.exists(dest_path):
            sysutils.rm_item(dest_path)
        sysutils.mk_link(src_path, dest_path)

    if osname == 'Linux':
        cmd = "sudo bash -c 'chown kraken:kraken %s/*'" % agent_dir
        subprocess.run(cmd, shell=True, check=True)


def update_agent(version):
    log.info('trying to update agent to new version: %s', version)

    # prepare /opt/kraken/VER directory
    dest_dir = prepare_dest_dir(version)

    # download binaries (kkagent and kktool) to prepared folder
    try:
        agent_path, tool_path = get_blobs(dest_dir)
    except Exception:
        log.exception('problem with downloading agent blob or writing it to disk, aborted agent update')
        return
    log.info('got blobs')

    # check binaries integrity
    try:
        cmd = [sys.executable, agent_path, 'check-integrity']
        subprocess.run(cmd, check=True)
        cmd = [sys.executable, tool_path, 'check-integrity']
        subprocess.run(cmd, check=True)
    except Exception:
        log.exception('blobs integrity check failed, aborted agent update')
        return
    log.info('integrity check passed')

    # now we can safely make links to new bins
    make_links_to_new_binaries(dest_dir)

    if osname == 'Linux':
        sysutils.rm_item('/opt/kraken/.shiv')
    elif osname == 'Windows':
        sysutils.rm_item('%USERPROFILE%\\.shiv')

    # start new kkagent
    log.info('restarting agent to new version: %s with python %s and args %s', version, sys.executable, sys.argv)
    os.execl(sys.executable, *sys.argv)
