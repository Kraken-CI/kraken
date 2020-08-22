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

import time
import socket
from urllib.parse import urlparse


def _is_service_open(addr, port, sock_type):
    s = socket.socket(socket.AF_INET, sock_type)
    s.settimeout(1)
    try:
        s.connect((addr, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()


def check_tcp_service(name, addr, port):
    attempt = 1
    trace = "checking TCP service %s on %s:%d..." % (name, addr, port)
    print("%s %d." % (trace, attempt))
    while not _is_service_open(addr, port, socket.SOCK_STREAM):
        if attempt < 3:
            time.sleep(2)
        elif attempt < 10:
            time.sleep(5)
        else:
            time.sleep(30)
        attempt += 1
        print("%s %d." % (trace, attempt))
    print("%s is up" % name)


def check_url(name, url, default_port):
    o = urlparse(url)
    check_tcp_service(name, o.hostname, o.port or default_port)


def check_postgresql(url):
    check_url('postgresql', url, 5432)
