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

import os
import json
import time
import logging
import datetime

from flask import request, send_file, abort

from . import consts

KKAGENT_DIR = os.environ.get('KKAGENT_DIR', '')

def serve_agent_blob(blob):
    #req = request.get_json()
    if blob not in ['agent', 'tool']:
         abort(404)

    p = os.path.join(KKAGENT_DIR, 'kk' + blob)
    return send_file(p)
