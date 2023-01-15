# Copyright 2020-2021 The Kraken Authors
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
import re
import logging
import xmlrpc.client

import pytimeparse
import dateutil.parser
import RestrictedPython
from RestrictedPython import compile_restricted
from RestrictedPython import limited_builtins

from . import consts
from . import schemaval
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
    try:
        byte_code = compile_restricted(schema_code, '<inline>', 'exec')
    except Exception as e:
        log.exception('schema compilation exception')
        msg = 'compilation error: ' + str(e)
        raise SchemaError(msg) from e

    my_locals = {}
    my_globals = {'__builtins__': limited_builtins,
                  '_getattr_': RestrictedPython.Guards.safer_getattr,
                  '_getiter_': RestrictedPython.Eval.default_guarded_getiter,
                  '_iter_unpack_sequence_': RestrictedPython.Guards.guarded_iter_unpack_sequence}


    try:
        exec(byte_code, my_globals, my_locals)  # pylint: disable=exec-used
    except Exception as e:
        log.exception('schema compilation exception')
        msg = 'compilation error: ' + str(e)
        raise SchemaError(msg) from e

    my_globals.update(my_locals)
    if context is None:
        context = {
            'is_ci': True,
            'is_dev': False,
        }
    ctx = SchemaCodeContext(branch.name, context)
    my_globals['ctx'] = ctx

    my_locals2 = {}
    try:
        exec('schema = stage(ctx)', my_globals, my_locals2)  # pylint: disable=exec-used
    except Exception as e:
        log.exception('schema compilation exception')
        msg = 'compilation error: ' + str(e)
        raise SchemaError(msg) from e
    schema = my_locals2['schema']

    # validate generated schema
    error = schemaval.validate(schema)
    if error:
        raise SchemaError(error)

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
    except SchemaError:
        raise
    except Exception:
        log.exception('unkown error in schema execution')
        raise

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
        for s in branch.stages:
            if s.deleted:
                continue
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
                        raise SchemaError("Secret '%s' does not exist" % value)

    # TODO: check if git url is valid according to giturlparse
    return schema_code, schema


def prepare_secrets(run):
    secrets = {}
    for s in run.stage.branch.project.secrets:
        if s.deleted:
            continue
        if s.kind == consts.SECRET_KIND_SSH_KEY:
            name = "KK_SECRET_USER_" + s.name
            secrets[name] = s.data['username']
            name = "KK_SECRET_KEY_" + s.name
            secrets[name] = s.data['key']
        elif s.kind == consts.SECRET_KIND_SIMPLE:
            name = "KK_SECRET_SIMPLE_" + s.name
            secrets[name] = s.data['secret']

    return secrets


def substitute_val(val, args):
    if isinstance(val, dict):
        return substitute_vars(val, args)
    if isinstance(val, list):
        list2 = []
        list2_masked = []
        for e in val:
            e2, e2_masked = substitute_val(e, args)
            list2.append(e2)
            list2_masked.append(e2_masked)
        return list2, list2_masked
    if not isinstance(val, str):
        return val, val

    val_masked = val
    secret_present = False
    for var in re.findall(r'#{[A-Za-z0-9_ ]+}', val):
        name = var[2:-1]
        if name in args:
            arg_val = args[name]
            if  not isinstance(arg_val, str):
                raise Exception("value '%s' of '%s' should have string type but has '%s'" % (str(arg_val), name, str(type(arg_val))))
            val = val.replace(var, arg_val)
            if name.startswith('KK_SECRET_'):
                val_masked = val_masked.replace(var, '******')
                secret_present = True
            else:
                val_masked = val_masked.replace(var, arg_val)

    if secret_present:
        return val, val_masked
    return val, val


def substitute_vars(fields, args):
    new_fields = {}
    new_fields_masked = {}
    for f, val in fields.items():
        val, val_masked = substitute_val(val, args)
        new_fields[f] = val
        new_fields_masked[f] = val_masked
    return new_fields, new_fields_masked


def prepare_new_planner_triggers(stage_id, new_triggers, prev_triggers, triggers):
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)

    log.info('stage: %d, triggers: new: %s, old: %s', stage_id, new_triggers, prev_triggers)

    # set up interval trigger
    if 'interval' in new_triggers:
        interval = int(pytimeparse.parse(new_triggers['interval']))
        if prev_triggers is None or 'interval' not in prev_triggers or 'interval_planner_job' not in triggers:
            args = (stage_id, consts.FLOW_KIND_CI, dict(reason='interval'))
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'interval', args, None,
                                  None, None, None, None, None, None, False, dict(seconds=interval))
            triggers['interval_planner_job'] = job['id']
            log.info('added new interval trigger - interval:%ds: next: %s', interval, job['next_run_time'])
        else:
            prev_interval = int(pytimeparse.parse(prev_triggers['interval']))
            if interval != prev_interval:
                job = planner.reschedule_job(triggers['interval_planner_job'], 'interval', dict(seconds=interval))
                log.info('rescheduled interval trigger - interval:%ds: next: %s', interval, job['next_run_time'])
    elif 'interval_planner_job' in triggers:
        planner.remove_job(triggers['interval_planner_job'])
        del triggers['interval_planner_job']
        log.info('deleted interval trigger')

    # set up date trigger
    if 'date' in new_triggers:
        run_date = dateutil.parser.parse(new_triggers['date'])
        if prev_triggers is None or 'date' not in prev_triggers or 'date_planner_job' not in triggers:
            args = (stage_id, consts.FLOW_KIND_CI, dict(reason='date'))
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'date', args, None,
                                  None, None, None, None, None, None, False, dict(run_date=str(run_date)))
            triggers['date_planner_job'] = job['id']
            log.info('added new date trigger - date:%s: next: %s', str(run_date), job['next_run_time'])
        else:
            prev_run_date = dateutil.parser.parse(prev_triggers['date'])
            if run_date != prev_run_date:
                job = planner.reschedule_job(triggers['date_planner_job'], 'date', dict(run_date=str(run_date)))
                log.info('rescheduled date trigger - date:%s: next: %s', str(run_date), job['next_run_time'])
    elif 'date_planner_job' in triggers:
        planner.remove_job(triggers['date_planner_job'])
        del triggers['date_planner_job']

    # set up cron trigger
    if 'cron' in new_triggers:
        cron_rule = new_triggers['cron']
        if prev_triggers is None or 'cron' not in prev_triggers or 'cron_planner_job' not in triggers:
            minutes, hours, days, months, dow = cron_rule.split()
            args = (stage_id, consts.FLOW_KIND_CI, dict(reason='cron'))
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'cron', args, None,
                                  None, None, None, None, None, None, False,
                                  dict(minute=minutes, hour=hours, day=days, month=months, day_of_week=dow))
            triggers['cron_planner_job'] = job['id']
            log.info('added new cron trigger - rule:%ds: next: %s', cron_rule, job['next_run_time'])
        else:
            prev_cron_rule = prev_triggers['cron']
            if cron_rule != prev_cron_rule:
                minutes, hours, days, months, dow = cron_rule.split()
                job = planner.reschedule_job(triggers['cron_planner_job'], 'cron',
                                             dict(minute=minutes, hour=hours, day=days, month=months, day_of_week=dow))
                log.info('rescheduled cron trigger - rule:%s: next: %s', cron_rule, job['next_run_time'])
    elif 'cron_planner_job' in triggers:
        planner.remove_job(triggers['cron_planner_job'])
        del triggers['cron_planner_job']

    # set up repo interval trigger
    if 'repo' in new_triggers:
        interval = int(pytimeparse.parse(new_triggers['repo']['interval']))
        if prev_triggers is None or 'repo' not in prev_triggers or 'repo_interval_planner_job' not in triggers:
            args = (stage_id, consts.FLOW_KIND_CI, dict(reason='repo_interval'))
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'repo_interval', args, None,
                                  None, None, None, None, None, None, False, dict(seconds=interval))
            triggers['repo_interval_planner_job'] = job['id']
            log.info('added new repo interval trigger - interval:%ds: next: %s', interval, job['next_run_time'])
        else:
            prev_interval = int(pytimeparse.parse(prev_triggers['repo']['interval']))
            if interval != prev_interval:
                job = planner.reschedule_job(triggers['repo_interval_planner_job'], 'interval', dict(seconds=interval))
                log.info('rescheduled repo interval trigger - interval:%ds: next: %s', interval, job['next_run_time'])
    elif 'repo_interval_planner_job' in triggers:
        planner.remove_job(triggers['repo_interval_planner_job'])
        del triggers['repo_interval_planner_job']
        log.info('deleted repo interval trigger')

    if triggers == {}:
        triggers['parent'] = True
