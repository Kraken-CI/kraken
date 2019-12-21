import os
import json
import logging
import datetime

from flask import make_response, abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
import pytimeparse
import dateutil.parser
import xmlrpc.client

from . import consts
from .models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult
from .models import Project
from .schema import execute_schema_code

log = logging.getLogger(__name__)


def create_project(project):
    project_rec = Project.query.filter_by(name=project['name']).one_or_none()
    if project_rec is not None:
        abort(400, "Project with name %s already exists" % project['name'])

    new_project = Project(name=project['name'], description=project.get('description', ''))
    db.session.commit()

    return new_project.get_json(), 201


def create_branch(project_id, branch):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(404, "Project not found")

    new_branch = Branch(project=project, name=branch['name'])
    db.session.commit()

    return new_branch.get_json(), 201


def get_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")
    return branch.get_json(with_cfg=True), 200


def _check_and_correct_stage_schema(branch, stage, prev_schema_code):
    if 'schema_code' in stage:
        schema_code = stage['schema_code']
        log.info('new schema_code %s', schema_code)
    elif prev_schema_code:
        schema_code = prev_schema_code
        log.info('prev schema_code %s', schema_code)
    else:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "trigger": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": []
    }'''

    # execute schema code
    try:
        schema = execute_schema_code(branch, schema_code)
    except Exception as e:
        abort(400, "Problem with executing stage schema code: %s" % e)

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
            if schema['parent'] == s.name and stage['name'] != s.name:
                found = True
                break
        if not found:
            abort(400, 'Cannot find parent stage %s' % schema['parent'])

    return schema_code, schema


def _prepare_new_planner_triggers(stage_id, new_triggers, prev_triggers, triggers):
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)

    if 'interval' in new_triggers:
        interval = int(pytimeparse.parse(new_triggers['interval']))
        if prev_triggers is None or 'interval' not in prev_triggers or 'interval_planner_job' not in triggers:
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'interval', (stage_id,), None,
                                  None, None, None, None, None, None, False, dict(seconds=int(interval)))
            triggers['interval_planner_job'] = job['id']
        else:
            prev_interval = int(pytimeparse.parse(prev_triggers['interval']))
            if interval != prev_interval:
                planner.reschedule_job(new_triggers['interval_planner_job'], 'interval', dict(seconds=int(interval)))
    elif 'interval_planner_job' in triggers:
            planner.remove_job(triggers['interval_planner_job'])
            del triggers['interval_planner_job']

    if 'date' in new_triggers:
        run_date = dateutil.parser.parse(new_triggers['date'])
        if prev_triggers is None or 'date' not in prev_triggers or 'date_planner_job' not in triggers:
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'date', (stage_id,), None,
                                  None, None, None, None, None, None, False, dict(run_date=str(run_date)))
            triggers['date_planner_job'] = job['id']
        else:
            prev_run_date = dateutil.parser.parse(prev_triggers['date'])
            if run_date != prev_run_date:
                planner.reschedule_job(new_triggers['date_planner_job'], 'date', dict(run_date=str(run_date)))
    elif 'date_planner_job' in triggers:
            planner.remove_job(triggers['date_planner_job'])
            del triggers['date_planner_job']

    if 'cron' in new_triggers:
        cron_rule = new_triggers['cron']
        if prev_triggers is None or 'cron' not in prev_triggers or 'cron_planner_job' not in triggers:
            minutes, hours, days, months, dow = cron_rule.split()
            job = planner.add_job('kraken.server.pljobs:trigger_run', 'cron', (stage_id,), None,
                                  None, None, None, None, None, None, False,
                                  dict(minute=minutes, hour=hours, day=days, month=months, day_of_week=dow))
            triggers['cron_planner_job'] = job['id']
        else:
            prev_cron_rule = prev_triggers['cron']
            if cron_rule != prev_cron_rule:
                minutes, hours, days, months, dow = cron_rule.split()
                planner.reschedule_job(new_triggers['cron_planner_job'], 'cron',
                                       dict(minute=minutes, hour=hours, day=days, month=months, day_of_week=dow))
    elif 'cron_planner_job' in triggers:
            planner.remove_job(triggers['cron_planner_job'])
            del triggers['cron_planner_job']

    if triggers == {}:
        triggers['parent'] = True


def create_stage(branch_id, stage):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    schema_code, schema = _check_and_correct_stage_schema(branch, stage, None)

    # create record
    new_stage = Stage(branch=branch, name=stage['name'], schema=schema, schema_code=schema_code)
    db.session.flush()

    triggers = {}
    _prepare_new_planner_triggers(new_stage.id, schema['triggers'], None, triggers)
    new_stage.triggers = triggers

    db.session.commit()

    return new_stage.get_json(), 201


def update_stage(stage_id, stage):
    stage_rec = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage_rec is None:
        abort(404, "Stage not found")

    if 'name' in stage:
        stage_rec.name = stage['name']

    if 'description' in stage:
        stage_rec.description = stage['description']

    if 'enabled' in stage:
        stage_rec.enabled = stage['enabled']

    if 'schema_code' in stage:
        _, schema = _check_and_correct_stage_schema(stage_rec.branch, stage, stage_rec.schema_code)
        stage_rec.schema = schema
        stage_rec.schema_code = stage['schema_code']
        flag_modified(stage_rec, 'schema')
        if stage_rec.triggers is None:
            stage_rec.triggers = {}
        _prepare_new_planner_triggers(stage_rec.id, schema['triggers'], stage_rec.schema['triggers'], stage_rec.triggers)
        flag_modified(stage_rec, 'triggers')
        log.info('new schema: %s', stage_rec.schema)

    if 'webhooks' in stage:
        stage_rec.webhooks = stage['webhooks']

    db.session.commit()

    result = stage_rec.get_json()
    log.info('result: %s', result)
    return result, 200


def delete_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    stage.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def get_stage_schema_as_json(stage_id, schema_code):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    try:
        schema = execute_schema_code(stage.branch, schema_code['schema_code'])
    except Exception as e:
        return dict(stage_id=stage_id, error=str(e)), 200

    schema = json.dumps(schema, indent=4, separators=(',', ': '))

    return dict(stage_id=stage_id, schema=schema), 200
