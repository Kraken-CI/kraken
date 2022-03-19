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

from . import utils


def _is_service_open(addr, port, sock_type):
    with socket.socket(socket.AF_INET, sock_type) as s:
        s.settimeout(1)
        try:
            s.connect((addr, port))
            s.shutdown(socket.SHUT_RDWR)
            return True
        except Exception:
            return False


def _parse_url_or_addr(url_addr, default_port=None):
    o = urlparse(url_addr)
    if o.hostname:
        host = o.hostname
        port = o.port or default_port
    else:
        host, port = utils.split_host_port(url_addr, default_port)

    return host, port


def is_service_open(url_addr, default_port=None):
    host, port = _parse_url_or_addr(url_addr, default_port)
    return _is_service_open(host, port, socket.SOCK_STREAM)


def wait_for_service(name, url_addr, default_port):
    host, port = _parse_url_or_addr(url_addr, default_port)

    attempt = 1
    trace = "checking TCP service %s on %s:%d..." % (name, host, port)
    print("%s %d." % (trace, attempt))
    while not _is_service_open(host, port, socket.SOCK_STREAM):
        if attempt < 3:
            time.sleep(2)
        elif attempt < 10:
            time.sleep(5)
        else:
            time.sleep(30)
        attempt += 1
        print("%s %d." % (trace, attempt))
    print("%s is up" % name)


def check_postgresql(url):
    wait_for_service('postgresql', url, 5432)
