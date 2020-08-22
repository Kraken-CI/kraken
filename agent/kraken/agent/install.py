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
ExecStart=/opt/kraken/kkagent -s %s -d %s run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
'''

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


def install_linux():
    dstr = distro.id()

    if dstr == 'ubuntu':
        # mute problems with sudo
        run('sudo bash -c \'echo "Set disable_coredump false" >> /etc/sudo.conf\'')

    # create kraken user
    if dstr in ['ubuntu', 'debian']:
        run('sudo useradd kraken -d %s -m -s /bin/bash -G sudo' % consts.AGENT_DIR)
    elif dstr in ['fedora', 'centos']:
        run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system' % consts.AGENT_DIR)
    elif 'suse' in dstr:
        run('sudo useradd kraken -d %s -m -s /bin/bash -G wheel --system -U' % consts.AGENT_DIR)
    else:
        raise Exception('distro %s is not supported yet' % dstr)

    # install bin files
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    dest_dir = update.get_dest_dir(kraken_version)
    if dest_dir.exists():
        run('sudo rm -rf %s' % dest_dir)
    run('sudo mkdir -p %s' % dest_dir)
    data_dir = Path(consts.AGENT_DIR) / 'data'
    run('sudo mkdir -p %s' % data_dir)
    run('sudo chown kraken:kraken %s' % dest_dir)
    tmp_dir = Path(tempfile.gettempdir())
    agent_path, tool_path = update.get_blobs(tmp_dir)
    run('sudo mv %s %s %s' % (agent_path, tool_path, dest_dir))
    run('sudo ln -s %s/kkagent /opt/kraken/kkagent' % dest_dir)
    run('sudo ln -s %s/kktool /opt/kraken/kktool' % dest_dir)
    run('sudo chown kraken:kraken %s/* /opt/kraken/*' % dest_dir)

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
