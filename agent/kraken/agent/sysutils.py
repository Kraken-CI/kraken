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
import array
import socket
import struct
import logging
import platform
import subprocess

from . import consts

osname = platform.system()
if osname == 'Linux':
    import fcntl


log = logging.getLogger(__name__)


def get_ifaces():
    lst = []

    if osname == 'Linux':
        max_possible = 128 # arbitrary. raise if needed.
        obytes = max_possible * 32
        deb = b'\0'
        names = array.array('B', deb * obytes)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            outbytes = struct.unpack('iL', fcntl.ioctl(
                s.fileno(),
                0x8912,  # SIOCGIFCONF
                struct.pack('iL', obytes, names.buffer_info()[0])
            ))[0]

        namestr = names.tobytes()

        for i in range(0, outbytes, 40):
            name = namestr[ i: i+16 ].split( deb, 1)[0]
            name = name.decode()
            #iface_name = namestr[ i : i+16 ].split( deb, 1 )[0]
            ip   = namestr[i+20:i+24]
            ip = f'{ip[0]}.{ip[1]}.{ip[2]}.{ip[3]}'
            lst.append((name, ip))

    elif osname == 'Windows':
        cmd = 'powershell.exe "Get-NetIPAddress -AddressFamily IPv4 | Select-object -property IPv4Address,InterfaceAlias |  ConvertTo-Csv -NoTypeInformation"'
        out = subprocess.check_output(cmd, shell=True)
        out = out.decode()
        for l in out.splitlines()[1:]:
            parts = l.split(',')
            ip = parts[0].strip('"')
            name = parts[1].strip('"')
            if name.lower().startswith('loopback'):
                name = 'lo'
            lst.append((name, ip))
    else:
        raise Exception('get_ifaces not implemented on %s' % osname)

    return lst


def get_my_ip(dest_addr):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            # doesn't even have to be reachable
            s.connect((dest_addr, 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = None
    return ip


def get_agent_dir():
    if osname == 'Windows':
        agent_dir = consts.AGENT_DIR_WIN
    else:
        agent_dir = consts.AGENT_DIR
    return os.path.expandvars(agent_dir)


def get_default_data_dir():
    data_dir = os.path.join(get_agent_dir(), 'data')
    return data_dir


def rm_item(path, check=True):
    if osname == 'Linux':
        cmd = f'sudo rm -f {path}'
    elif osname == 'Windows':
        cmd = f'powershell Remove-Item -Recurse -Force {path}'
    subprocess.run(cmd, shell=True, check=check)


def mk_link(src, dest):
    if osname == 'Linux':
        cmd = f'sudo ln -s {src} {dest}'
    elif osname == 'Windows':
        cmd = f'mklink {dest} {src}'
    subprocess.run(cmd, shell=True, check=True)
