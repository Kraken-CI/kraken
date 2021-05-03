# Copyright 2020-2021 The Kraken Authors
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

import socket
import fcntl
import struct
import array


def get_ifaces():
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

    lst = []
    for i in range(0, outbytes, 40):
        name = namestr[ i: i+16 ].split( deb, 1)[0]
        name = name.decode()
        #iface_name = namestr[ i : i+16 ].split( deb, 1 )[0]
        ip   = namestr[i+20:i+24]
        ip = f'{ip[0]}.{ip[1]}.{ip[2]}.{ip[3]}'
        lst.append((name, ip))
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
