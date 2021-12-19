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

_CFG = {}


def set_config(config):
    global _CFG  # pylint: disable=global-statement
    _CFG = config


def get_config():
    return _CFG


def merge(config):
    global _CFG  # pylint: disable=global-statement

    changes = {}
    for k, v in config.items():
        if k not in _CFG or _CFG[k] != v:
            changes[k] = v
            _CFG[k] = v

    return changes


def get(name, default_value=None):
    if default_value is not None:
        return _CFG.get(name, default_value)
    return _CFG[name]
