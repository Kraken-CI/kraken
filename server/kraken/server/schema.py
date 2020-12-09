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

import logging

import RestrictedPython
from RestrictedPython import compile_restricted
from RestrictedPython import limited_builtins

from .models import Secret


log = logging.getLogger(__name__)


class SchemaError(Exception):
    pass


class SchemaCodeContext:
    def __init__(self, branch_name, context):
        self.branch_name = branch_name
        for k, v in context.items():
            setattr(self, k, v)


def execute_schema_code(branch, schema_code, context=None):
    # TODO: use starlark-go for executing schema code
    # for now RestrictedPython is used
    byte_code = compile_restricted(schema_code, '<inline>', 'exec')

    my_locals = {}
    my_globals = {'__builtins__': limited_builtins,
                  '_getattr_': RestrictedPython.Guards.safer_getattr,
                  '_getiter_': RestrictedPython.Eval.default_guarded_getiter,
                  '_iter_unpack_sequence_': RestrictedPython.Guards.guarded_iter_unpack_sequence}


    exec(byte_code, my_globals, my_locals)  # pylint: disable=exec-used

    my_globals.update(my_locals)
    if context is None:
        context = {
            'is_ci': True,
            'is_dev': False,
        }
    ctx = SchemaCodeContext(branch.name, context)
    my_globals['ctx'] = ctx

    my_locals2 = {}
    exec('schema = stage(ctx)', my_globals, my_locals2)  # pylint: disable=exec-used
    schema = my_locals2['schema']

    return schema


def check_and_correct_stage_schema(branch, stage_name, schema_code, context=None):
    if not schema_code:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "hello world",
            "steps": [{
                "tool": "shell",
                "cmd": "echo 'hello world'"
            }],
            "environments": [{
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }'''
    log.info('schema_code %s', schema_code)

    # execute schema code
    try:
        schema = execute_schema_code(branch, schema_code, context)
    except Exception as e:
        raise SchemaError("Problem with executing stage schema code: %s" % e)

    # fill missing parts in schema
    if 'jobs' not in schema:
        schema['jobs'] = []

    if 'configs' not in schema:
        schema['configs'] = []

    if 'parent' not in schema or schema['parent'] == '':
        schema['parent'] = 'root'

    if 'triggers' not in schema or schema['triggers'] == {}:
        schema['triggers'] = {'parent': True}

    if 'parameters' not in schema:
        schema['parameters'] = []

    # check parent in schema
    if schema['parent'] != 'root':
        found = False
        for s in branch.stages.filter_by(deleted=None):
            if schema['parent'] == s.name and stage_name != s.name:
                found = True
                break
        if not found:
            raise SchemaError('Cannot find parent stage %s' % schema['parent'])

    # check job_names and secrets
    job_names = set()
    for job in schema['jobs']:
        # check names
        if job['name'] in job_names:
            raise SchemaError("Two jobs with the same name '%s'" % job['name'])

        job_names.add(job['name'])

        # check secrets
        for step in job['steps']:
            for field, value in step.items():
                if field in ['access-token', 'ssh-key']:
                    secret = Secret.query.filter_by(project=branch.project, name=value).one_or_none()
                    if secret is None:
                        raise SchemaError("Secret '%s' does not exists" % value)

    # TODO: check if git url is valid according to giturlparse
    return schema_code, schema
