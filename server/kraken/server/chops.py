# Copyright 2023 The Kraken Authors
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
from urllib.parse import urlparse

import clickhouse_driver

from . import consts


def get_clickhouse_url():
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    return ch_url


def get_clickhouse():
    ch_url = get_clickhouse_url()
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)
    return ch
