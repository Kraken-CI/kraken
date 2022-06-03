# Copyright 2022 The Kraken Authors
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

import zipfile

from kraken.server import toolops


def test_package_tool():

    tool_file = 'tests/example_tool/tool.json'

    meta, tf, file_num = toolops.package_tool(tool_file)

    fields = ['name', 'description', 'location', 'entry', 'parameters']
    for f in fields:
        assert f in meta

    assert meta['name'] == 'example_tool'
    assert meta['location'] == '.'
    assert meta['entry'] == 'main'
    assert meta['parameters'] is not None

    assert file_num > 50
    assert file_num < 100

    with zipfile.ZipFile(tf, "r") as pz:
        assert 'main.py' in pz.namelist()
        assert 'tool.json' in pz.namelist()
        assert 'requirements.txt' in pz.namelist()
        assert 'vendor/bin/pycvs' in pz.namelist()
