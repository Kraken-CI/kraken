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
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from . import config
from . import consts


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


def get_dest_dir(version):
    dest_dir = Path(consts.AGENT_DIR) / version
    return dest_dir


def prepare_dest_dir(version):
    dest_dir = get_dest_dir(version)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    return dest_dir


def make_links_to_new_binaries(dest_dir):
    if os.path.exists('/opt/kraken/kkagent'):
        os.unlink('/opt/kraken/kkagent')
    cmd = 'ln -s %s/kkagent /opt/kraken/kkagent' % dest_dir
    subprocess.run(cmd, shell=True, check=True)

    if os.path.exists('/opt/kraken/kktool'):
        os.unlink('/opt/kraken/kktool')
    cmd = 'ln -s %s/kktool /opt/kraken/kktool' % dest_dir
    subprocess.run(cmd, shell=True, check=True)


def update_agent(version):
    log.info('trying to update agent to new version: %s', version)

    # prepare /opt/kraken/VER directory
    dest_dir = prepare_dest_dir(version)

    # download binaries (kkagent and kktool) to prepared folder
    try:
        agent_path, tool_path = get_blobs(dest_dir)
    except:
        log.exception('problem with downloading agent blob or writing it to disk, aborted agent update')
        return
    log.info('got blobs')

    # check binaries integrity
    try:
        cmd = [agent_path, 'check-integrity']
        subprocess.run(cmd, check=True)
        cmd = [tool_path, 'check-integrity']
        subprocess.run(cmd, check=True)
    except:
        log.exception('blobs integrity check failed, aborted agent update')
        return
    log.info('integrity check passed')

    # now we can safely make links to new bins
    make_links_to_new_binaries(dest_dir)

    cmd = 'rm -rf /opt/kraken/.shiv'
    subprocess.run(cmd, shell=True, check=True)

    # start new kkagent
    log.info('restarting agent to new version: %s', version)
    os.execl('/opt/kraken/kkagent', '/opt/kraken/kkagent', *sys.argv[1:])
