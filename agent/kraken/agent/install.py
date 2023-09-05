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

import logging
import tempfile
import platform
import subprocess
from pathlib import Path

osname = platform.system()
if osname == 'Linux':
    import pwd
    import grp


import distro
import pkg_resources

from . import update
from . import consts
from . import config

log = logging.getLogger(__name__)


SYSTEMD_SERVICE = '''[Unit]
Description=Kraken Agent
Wants=network-online.target
After=network-online.target
After=time-sync.target

[Service]
User=kraken
ExecStart=/opt/kraken/kkagent run
Restart=on-failure
RestartSec=5s
EnvironmentFile=/opt/kraken/kraken.env

[Install]
WantedBy=multi-user.target
'''

KRAKEN_ENV = '''# address of kraken server
KRAKEN_SERVER_ADDR={server_addr}

# address of clickhouse-proxy, used for sending logs there
KRAKEN_CLICKHOUSE_ADDR={clickhouse_addr}

# directory with data dir, optional
KRAKEN_DATA_DIR={data_dir}

# directory with tools for Kraken, optional
KRAKEN_TOOLS_DIRS={tools_dirs}

# currently installed system ID
KRAKEN_SYSTEM_ID={system_id}
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
        elif dstr in ['fedora', 'centos', 'rocky']:
            run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system' % consts.AGENT_DIR)
        elif 'suse' in dstr:
            run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system -U' % consts.AGENT_DIR)
        else:
            raise Exception('distro %s is not supported yet' % dstr)  # pylint: disable=raise-missing-from

    # kraken user with no sudo password and disabled requiretty
    run("sudo sed -i 's/^.*requiretty/Defaults !requiretty/' /etc/sudoers")
    run("sudo bash -c \"echo 'Defaults !requiretty' >> /etc/sudoers\"")
    run("sudo bash -c \"echo 'kraken ALL = NOPASSWD: ALL' > /etc/sudoers.d/kraken\"")

    # add to docker group if present
    try:
        grp.getgrnam('docker')
        if dstr in ['ubuntu', 'debian']:
            run('sudo usermod -a -G docker kraken')
        elif dstr in ['fedora', 'centos', 'rocky']:
            run('sudo usermod -aG docker kraken')
        elif 'suse' in dstr:
            run('sudo usermod -a kraken -G docker')
        else:
            raise Exception('distro %s is not supported yet' % dstr)
    except KeyError:
        log.info('no docker group')

    # TODO: add to lxd group if present

    # install bin files
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    dest_dir = update.get_dest_dir(kraken_version)
    run('sudo rm -rf %s' % dest_dir)
    run('sudo mkdir -p %s' % dest_dir)
    data_dir = config.get('data_dir')
    if not data_dir:
        data_dir = Path(consts.AGENT_DIR) / 'data'
    run('sudo mkdir -p %s' % data_dir)
    run('sudo chown -R kraken:kraken %s' % consts.AGENT_DIR)
    run('sudo chmod a+rx %s' % consts.AGENT_DIR)
    run('sudo chmod a+rx %s' % dest_dir)
    run('sudo chmod a+rx %s' % data_dir)
    tmp_dir = Path(tempfile.gettempdir())
    agent_path, tool_path = update.get_blobs(tmp_dir)
    run('sudo mv %s %s %s' % (agent_path, tool_path, dest_dir))

    # prepare kraken env file
    kenv = KRAKEN_ENV.format(server_addr=config.get('server'),
                             data_dir=data_dir,
                             tools_dirs=config.get('tools_dirs') or '',
                             clickhouse_addr=config.get('clickhouse_addr') or '',
                             system_id=config.get('system_id', '') or '')
    run('sudo bash -c \'echo "%s" > /opt/kraken/kraken.env\'' % kenv)

    run("sudo bash -c 'chown kraken:kraken %s/* /opt/kraken/*'" % dest_dir)

    update.make_links_to_new_binaries(dest_dir)

    # setup kraken agent service in systemd
    sysd_dest = '/lib/systemd/system'
    if 'suse' in dstr:
        sysd_dest = '/usr/lib/systemd/system'
    run('sudo bash -c \'echo "%s" > %s/kraken-agent.service\'' % (SYSTEMD_SERVICE, sysd_dest))
    run('sudo systemctl daemon-reload')
    run('sudo systemctl enable kraken-agent.service')
    run('sudo systemctl start kraken-agent.service')
    run('sudo systemctl status kraken-agent.service')


def install():
    s = platform.system()
    if s == 'Linux':
        install_linux()
    elif s == 'Windows':
        install_windows()
    else:
        raise Exception('system %s is not supported yet' % s)
