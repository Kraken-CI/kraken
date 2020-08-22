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


def update_agent(version):
    log.info('trying to update agent to new version: %s', version)

    dest_dir = prepare_dest_dir(version)

    try:
        agent_path, tool_path = get_blobs(dest_dir)
    except:
        log.exception('problem with downloading agent blob or writing it to disk, aborted agent update')
        return
    log.info('got blobs')

    try:
        cmd = [agent_path, 'check-integrity']
        subprocess.run(cmd, check=True)
        cmd = [tool_path, 'check-integrity']
        subprocess.run(cmd, check=True)
    except:
        log.exception('blobs integrity check failed, aborted agent update')
        return
    log.info('integrity check passed')

    log.info('restarting agent to new version: %s', version)
    os.execl(agent_path, agent_path, *sys.argv[1:])
