# Copyright 2021 The Kraken Authors
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
import datetime

import pytz

log = logging.getLogger(__name__)


def utcnow():
    return datetime.datetime.now(pytz.utc)


def split_host_port(addr, default_port):
    parts = addr.split(':')
    host = parts[0]
    if len(parts) == 1:
        if default_port is None:
            raise Exception("format of address '%s' is incorrect" % addr)
        port = default_port
    else:
        port = int(parts[1])
    return host, port
