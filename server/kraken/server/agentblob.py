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
