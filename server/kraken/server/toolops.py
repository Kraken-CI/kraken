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

import os
import json
import shutil
import logging
import zipfile
import tempfile
import subprocess

log = logging.getLogger(__name__)


def run(cmd, check=True, cwd=None, capture_output=False, text=None):
    log.info("execute '%s' in '%s'", cmd, cwd)
    p = subprocess.run(cmd, shell=True, check=check, cwd=cwd, capture_output=capture_output, text=text)
    return p


def install_reqs(tool_file):
    tool_dir = os.path.abspath(os.path.dirname(tool_file))
    vendor_dir = os.path.join(tool_dir, 'vendor')
    reqs_txt_path = os.path.join(tool_dir, 'requirements.txt')

    # install requirements to vendor dir
    if os.path.exists(reqs_txt_path):
        if os.path.exists(vendor_dir):
            shutil.rmtree(vendor_dir)
        os.makedirs(vendor_dir)

        cmd = 'python3 -m pip install -r requirements.txt --target=./vendor'
        run(cmd, cwd=tool_dir)

    return tool_dir


def package_tool(tool_file):
    # load file and parse as JSON
    with open(tool_file) as fp:
        meta = json.load(fp)

    tool_dir = install_reqs(tool_file)

    # store tool files in zip package
    tf = tempfile.NamedTemporaryFile(prefix='kkci-pkg-', suffix='.zip', delete=True)
    with zipfile.ZipFile(tf, "w") as pz:
        for root, _, files in os.walk(tool_dir):
            for name in files:
                if name.endswith(('.pyc', '~')):
                    continue
                if name == 'tool.zip':
                    continue
                p = os.path.join(root, name)
                n = os.path.relpath(p, tool_dir)
                pz.write(p, arcname=n)

    tf.seek(0)

    return meta, tf, len(pz.namelist())
