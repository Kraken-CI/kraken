import logging
import datetime

from flask import make_response, abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
import pytimeparse
import dateutil.parser
from jsonrpcclient.clients.http_client import HTTPClient

import consts
from models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult
from models import Project

log = logging.getLogger(__name__)


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


def _check_and_correct_stage_schema(branch, stage):
    if 'schema' in stage:
        schema = stage['schema']
    else:
        schema = {}

    # fill missing parts in schema
    if 'jobs' not in schema:
        schema['jobs'] = []

    if 'configs' not in schema:
        schema['configs'] = []

    if 'parent' not in schema or schema['parent'] == '':
        schema['parent'] = 'root'

    if 'trigger' not in schema or schema['trigger'] == {}:
        schema['trigger'] = {'parent': True}

    # check parent in schema
    if schema['parent'] != 'root':
        found = False
        for s in branch.stages.filter_by(deleted=None):
            if schema['parent'] == s.name and stage['name'] != s.name:
                found = True
                break
        if not found:
            abort(400, 'Cannot find parent stage %s' % schema['parent'])

    stage['schema'] = schema


def _prepare_new_planner_trigger(stage_id, trigger, prev_trigger):
    planner = HTTPClient("http://localhost:8000")

    if 'interval' in trigger:
        interval = int(pytimeparse.parse(trigger['interval']))
        if prev_trigger is None or 'interval' not in prev_trigger or 'interval_planner_job' not in prev_trigger:
            response = planner.request('add_job', func='pljobs:trigger_run', trigger='interval', args=(stage_id,), seconds=int(interval))
            trigger['interval_planner_job'] = response.data.result['id']
        else:
            prev_interval = int(pytimeparse.parse(prev_trigger['interval']))
            if interval != prev_interval:
                response = planner.request('reschedule_job', trigger='interval', seconds=int(interval))
    elif 'interval_planner_job' in trigger:
            response = planner.request('remove_job', trigger['interval_planner_job'])
            del trigger['interval_planner_job']


    if 'date' in trigger:
        run_date = dateutil.parser.parse(trigger['date'])
        if prev_trigger is None or 'date' not in prev_trigger or 'date_planner_job' not in prev_trigger:
            response = planner.request('add_job', func='pljobs:trigger_run', trigger='date', args=(stage_id,), run_date=str(run_date))
            trigger['date_planner_job'] = response.data.result['id']
        else:
            prev_run_date = dateutil.parser.parse(prev_trigger['date'])
            if run_date != prev_run_date:
                response = planner.request('reschedule_job', trigger='date', run_date=str(run_date))
    elif 'date_planner_job' in trigger:
            response = planner.request('remove_job', trigger['date_planner_job'])
            del trigger['date_planner_job']

    if 'cron' in trigger:
        cron_rule = trigger['cron']
        if prev_trigger is None or 'cron' not in prev_trigger or 'cron_planner_job' not in prev_trigger:
            minutes, hours, days, months, dow = cron_rule.split()
            response = planner.request('add_job', func='pljobs:trigger_run', trigger='cron', args=(stage_id,),
                                       minute=minutes, hour=hours, day=days, month=months, day_of_week=dow)
            trigger['cron_planner_job'] = response.data.result['id']
        else:
            prev_cron_rule = prev_trigger['cron']
            if cron_rule != prev_cron_rule:
                minutes, hours, days, months, dow = cron_rule.split()
                response = planner.request('reschedule_job', trigger='cron',
                                           minute=minutes, hour=hours, day=days, month=months, day_of_week=dow)
    elif 'cron_planner_job' in trigger:
            response = planner.request('remove_job', trigger['cron_planner_job'])
            del trigger['cron_planner_job']

    if trigger == {}:
        trigger['parent'] = True


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

    _check_and_correct_stage_schema(branch, stage)

    # create record
    new_stage = Stage(branch=branch, name=stage['name'])
    db.session.flush()

    _prepare_new_planner_trigger(new_stage.id, stage['schema']['trigger'], None)
    new_stage.schema=stage['schema']

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

    if 'schema' in stage:
        _check_and_correct_stage_schema(stage_rec.branch, stage)
        _prepare_new_planner_trigger(stage_rec.id, stage['schema']['trigger'], stage_rec.schema['trigger'])
        stage_rec.schema = stage['schema']

    db.session.commit()

    return stage_rec.get_json(), 200


def delete_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    stage.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200
