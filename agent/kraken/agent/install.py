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

import pwd
import tempfile
import platform
import subprocess
from pathlib import Path

import distro
import pkg_resources

from . import config
from . import update
from . import consts

SYSTEMD_SERVICE = '''[Unit]
Description=Kraken Agent
Wants=network-online.target
After=network-online.target
After=time-sync.target

[Service]
User=kraken
ExecStart=/opt/kraken/kkagent run -s %s -d %s
Restart=on-failure
RestartSec=5s
EnvironmentFile=/opt/kraken/kraken.env

[Install]
WantedBy=multi-user.target
'''

KRAKEN_ENV = '''# address of clickhouse-proxy, used for sending logs there
KRAKEN_CLICKHOUSE_ADDR=

# address of minio, used for storing and retrieving build artifacts and for a cache
KRAKEN_MINIO_ADDR=
'''

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


def install_linux():
    dstr = distro.id()

    if dstr == 'ubuntu':
        # mute problems with sudo
        run('sudo bash -c \'echo "Set disable_coredump false" >> /etc/sudo.conf\'')

    # create kraken user
    try:
        pwd.getpwnam('kraken')
    except Exception:
        if dstr in ['ubuntu', 'debian']:
            run('sudo useradd kraken -d %s -m -s /bin/bash -G sudo' % consts.AGENT_DIR)
        elif dstr in ['fedora', 'centos']:
            run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system' % consts.AGENT_DIR)
        elif 'suse' in dstr:
            run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system -U' % consts.AGENT_DIR)
        else:
            raise Exception('distro %s is not supported yet' % dstr)  # pylint: disable=raise-missing-from

    # install bin files
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    dest_dir = update.get_dest_dir(kraken_version)
    if dest_dir.exists():
        run('sudo rm -rf %s' % dest_dir)
    run('sudo mkdir -p %s' % dest_dir)
    data_dir = Path(consts.AGENT_DIR) / 'data'
    run('sudo mkdir -p %s' % data_dir)
    run('sudo chown -R kraken:kraken %s' % consts.AGENT_DIR)
    tmp_dir = Path(tempfile.gettempdir())
    agent_path, tool_path = update.get_blobs(tmp_dir)
    run('sudo mv %s %s %s' % (agent_path, tool_path, dest_dir))

    # prepare kraken env file
    run('sudo bash -c \'echo "%s" > /opt/kraken/kraken.env\'' % KRAKEN_ENV)

    run('sudo chown kraken:kraken %s/* /opt/kraken/*' % dest_dir)

    update.make_links_to_new_binaries(dest_dir)

    run('sudo chown kraken:kraken /opt/kraken/*')

    # setup kraken agent service in systemd
    svc = SYSTEMD_SERVICE % (config.get('server'), data_dir)
    sysd_dest = '/lib/systemd/system'
    if 'suse' in dstr:
        sysd_dest = '/usr/lib/systemd/system'
    run('sudo bash -c \'echo "%s" > %s/kraken-agent.service\'' % (svc, sysd_dest))
    run('sudo systemctl daemon-reload')
    run('sudo systemctl enable kraken-agent.service')
    run('sudo systemctl start kraken-agent.service')
    run('sudo systemctl status kraken-agent.service')


def install():
    s = platform.system()
    if s == 'Linux':
        install_linux()
    else:
        raise Exception('system %s is not supported yet' % s)
