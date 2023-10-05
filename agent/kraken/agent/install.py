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
import logging
import tempfile
import platform
import subprocess
from pathlib import Path

import distro
import pkg_resources

from . import update
from . import consts
from . import config

osname = platform.system()
if osname == 'Linux':
    import pwd
    import grp

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
    print('cmd:', cmd)
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


PS_CREATE_KRAKEN_USER = """$SecPassword = ConvertTo-SecureString {kraken_password} -AsPlainText -Force
$UserID = Get-LocalUser -Name {kraken_user} -ErrorAction SilentlyContinue
if ($UserID) {{
    Write-Host "{kraken_user} admin account already exists"
}} else {{
    New-LocalUser {kraken_user} -Password $SecPassword -FullName {kraken_user} -Description "Kraken user for kkagent service"
    # get admin group name
    $SID = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-32-544")
    $AdminGroupName = $SID.Translate([System.Security.Principal.NTAccount]).Value.Split('\\')[-1]
    Add-LocalGroupMember -Group $AdminGroupName -Member {kraken_user}
    Write-Host "Created {kraken_user} account with admin rights"
}}
"""

PS_SETUP_SERVICE = """class nssm {{
    [string]$NSSMPath

    nssm([string] $Path) {{
        $this.NSSMPath = $Path
    }}

    Run($Cmd) {{
        Write-Host "$($this.NSSMPath) $Cmd"
        $p = Start-Process -PassThru -NoNewWindow -Wait -FilePath $this.NSSMPath -ArgumentList $Cmd
        if ($p.ExitCode -gt 0) {{
            throw "NSSM command failed"
        }}
    }}
}}

function Setup-Service([string] $DestDir, [string] $KrakenUser, [string] $KrakenPassword)
{{

    $NSSMPath = Join-Path $DestDir 'nssm-2.24\\win64\\nssm.exe'
    Write-Host "Check path to NSSM: $NSSMPath"
    if (Test-Path -Path $NSSMPath -PathType Leaf) {{
        Write-Host "Path to existing NSSM: $NSSMPath"
    }} else {{
        Invoke-WebRequest 'http://nssm.cc/release/nssm-2.24.zip' -OutFile 'nssm-2.24.zip'
        Expand-Archive 'nssm-2.24.zip' -DestinationPath $DestDir
        Remove-Item 'nssm-2.24.zip'
        Write-Host "Downloaded NSSM: $NSSMPath"
    }}

    # Set the path to your Python executable and script
    $PythonPath = Get-Command 'python.exe' | Select -ExpandProperty 'path'
    Write-Host "Path to Python: $PythonPath"

    # Set the service name and description
    $ServiceName = 'kkagent'
    $ServiceDescription = 'Kraken CI Agent'

    $NSSM = [nssm]::new($NSSMPath)

    # Check if the service exists or not
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service.Length -gt 0) {{
        # it exists, so just restart using NSSM
        $NSSM.Run("restart $ServiceName")
    }} else {{
        # it does not exist, so install the service using NSSM
        $NSSM.Run("install $ServiceName `"$PythonPath`" $DestDir\\kkagent run")
        $NSSM.Run("set $ServiceName DisplayName $ServiceName")
        $NSSM.Run("set $ServiceName Description '$ServiceDescription'")
        $NSSM.Run("set $ServiceName AppDirectory $DestDir")
        $NSSM.Run("set $ServiceName AppStdout $DestDir\\out.log")
        $NSSM.Run("set $ServiceName AppStderr $DestDir\\err.log")
        $ComputerName = Get-WmiObject -Namespace 'root\\cimv2' -Class 'Win32_ComputerSystem' | Select -ExpandProperty 'Name'
        $NSSM.Run("set $ServiceName ObjectName $ComputerName\\$KrakenUser $KrakenPassword")

        $NSSM.Run("set $ServiceName AppEnvironmentExtra KRAKEN_SERVER_ADDR={server_addr} KRAKEN_CLICKHOUSE_ADDR={clickhouse_addr} KRAKEN_DATA_DIR={data_dir} KRAKEN_TOOLS_DIRS={tools_dirs} KRAKEN_SYSTEM_ID={system_id}")

        $NSSM.Run("start $ServiceName")
    }}

    $Status = Get-Service $ServiceName | Select -ExpandProperty 'Status'

    if ($Status -ne 'Running') {{
        throw "$ServiceName service did not start correctly"
    }}

    Write-Host 'Kraken Agent service configured'
}}

Setup-Service 'c:\\kraken' {kraken_user} {kraken_password}
"""

def _powershell(code):
    f = tempfile.NamedTemporaryFile(delete=False, suffix='.ps1')
    f.write(bytes(code, 'utf-8'))
    f.close()
    cmd = 'powershell.exe -ExecutionPolicy Bypass -Command "& %s"' % f.name
    print('CMD', cmd)
    run(cmd)
    os.unlink(f.name)


def install_windows():
    # create kraken user
    ps = PS_CREATE_KRAKEN_USER.format(kraken_user='kraken',
                                      kraken_password='kraken')
    _powershell(ps)

    # install bin files
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    dest_dir = update.get_dest_dir(kraken_version)
    if os.path.exists(dest_dir):
        run('rmdir /s /q %s' % dest_dir)
    run('mkdir %s' % dest_dir)
    data_dir = config.get('data_dir')
    if not data_dir:
        data_dir = Path(consts.AGENT_DIR) / 'data'
    if not os.path.exists(data_dir):
        run('mkdir %s' % data_dir)
    tmp_dir = Path(tempfile.gettempdir())
    agent_path, tool_path = update.get_blobs(tmp_dir)
    run('move %s %s' % (agent_path, dest_dir))
    run('move %s %s' % (tool_path, dest_dir))

    update.make_links_to_new_binaries(dest_dir)

    # setup service
    ps = PS_SETUP_SERVICE.format(kraken_user='kraken',
                                 kraken_password='kraken',
                                 server_addr=config.get('server'),
                                 data_dir=data_dir,
                                 tools_dirs=config.get('tools_dirs') or '',
                                 clickhouse_addr=config.get('clickhouse_addr') or '',
                                 system_id=config.get('system_id', '') or '')
    _powershell(ps)


def install():
    s = platform.system()
    if s == 'Linux':
        install_linux()
    elif s == 'Windows':
        install_windows()
    else:
        raise Exception('system %s is not supported yet' % s)
