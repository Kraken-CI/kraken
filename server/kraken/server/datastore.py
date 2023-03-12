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

import json
import logging

import jq
import jsonpatch
from sqlalchemy.orm.attributes import flag_modified


from .models import db


log = logging.getLogger(__name__)


def handle_data(job, step, data):
    operation = step.fields.get('operation', 'set')
    scope = step.fields.get('scope', 'flow')
    ptr = step.fields.get('json_pointer', '/')
    value = step.fields.get('value', None)

    if operation not in ['set', 'jq', 'jsonpatch']:
        raise Exception('incorrect operation %s, should be one of set, jq, jsonpatch' % operation)

    if value:
        data = value

    log.info('handle_data %s %s %s', job, step, data)

    # get proper db entity and field according indicated scope
    if scope == 'project':
        entity = job.run.flow.branch.project
        data_field_name = 'user_data'
    elif scope == 'branch':
        entity = job.run.flow.branch
        data_field_name = 'user_data'
    elif scope == 'branch-ci':
        entity = job.run.flow.branch
        data_field_name = 'user_data_ci'
    elif scope == 'branch-dev':
        entity = job.run.flow.branch
        data_field_name = 'user_data_dev'
    elif scope in ['flow', '']:
        entity = job.run.flow
        data_field_name = 'user_data'
    else:
        log.warning('incorrect scope %s, should be one of project, branch, branch-ci, branch-dev, flow', scope)
        return

    # get current user data from database
    user_data = getattr(entity, data_field_name)

    # prepare data provided by user according to specified operation
    if operation == 'set':
        try:
            data = json.loads(data)
        except Exception:
            log.exception('wrong json data: %s', data)
            return
    elif operation == 'jq':
        try:
            q = jq.compile(data)
        except Exception:
            log.exception('wrong jq expression: %s', data)
            return
    elif operation == 'jsonpatch':
        try:
            patch = jsonpatch.JsonPatch.from_string(data)
        except Exception:
            log.exception('wrong jsonpatch expression: %s', data)
            return

    ptr = ptr.strip('/')
    if ptr:
        # replace user_data under position indicated by json pointer
        parts = ptr.split('/')
        user_data = getattr(entity, data_field_name)
        for idx, p in enumerate(parts):
            if p.isdigit():
                p = int(p)
            if idx != len(parts) - 1:
                user_data = user_data[p]
            else:
                if operation == 'set':
                    user_data[p] = data
                elif operation == 'jq':
                    user_data[p] = q.input(user_data[p]).first()
                elif operation == 'jsonpatch':
                    user_data[p] = patch.apply(user_data[p])
    else:
        # set new data on root level
        if operation == 'set':
            new_user_data = data
        elif operation == 'jq':
            new_user_data = q.input(user_data).first()
        elif operation == 'jsonpatch':
            new_user_data = patch.apply(user_data)

        setattr(entity, data_field_name, new_user_data)

    flag_modified(entity, data_field_name)
    db.session.commit()
