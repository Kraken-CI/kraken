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
from .models import db, Branch, Flow, Run, Stage, Job, Step, Executor, ExecutorGroup, Tool, TestCaseResult, Secret, ExecutorAssignment
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


def update_project(project_id, project):
    project_rec = Project.query.filter_by(id=project_id).one_or_none()
    if project_rec is None:
        abort(404, "Project not found")

    if 'webhooks' in project:
        project_rec.webhooks = project['webhooks']

    db.session.commit()

    result = project_rec.get_json()
    log.info('result: %s', result)
    return result, 200


def get_project(project_id):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    return project.get_json(), 200


def get_projects():
    q = Project.query
    projects = []
    for p in q.all():
        projects.append(p.get_json())
    return {'items': projects, 'total': len(projects)}, 200


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


def create_secret(project_id, secret):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    if secret['kind'] == 'ssh-key':
        kind = consts.SECRET_KIND_SSH_KEY
        data = dict(username=secret['username'],
                    key=secret['key'])
    elif secret['kind'] == 'simple':
        kind = consts.SECRET_KIND_SIMPLE
        data = dict(secret=secret['secret'])
    else:
        abort(400, "Wrong data")

    s = Secret(project=project, name=secret['name'], kind=kind, data=data)
    db.session.commit()

    return s.get_json(), 201


def update_secret(secret_id, secret):
    secret_rec = Secret.query.filter_by(id=secret_id).one_or_none()
    if secret_rec is None:
        abort(404, "Secret not found")

    log.info('secret %s', secret)
    if 'name' in secret:
        old_name = secret_rec.name
        secret_rec.name = secret['name']
        log.info('changed name from %s to %s', old_name, secret_rec.name)

    if secret_rec.kind == consts.SECRET_KIND_SIMPLE:
        if 'secret' in secret and secret['secret'] != '******':
            secret_rec.data['secret'] = secret['secret']
    elif secret_rec.kind == consts.SECRET_KIND_SSH_KEY:
        if 'username' in secret:
            secret_rec.data['username'] = secret['username']
        if 'key' in secret and secret['key'] != '******':
            secret_rec.data['key'] = secret['key']
    flag_modified(secret_rec, 'data')

    db.session.commit()

    result = secret_rec.get_json()
    log.info(result)
    return result, 200


def delete_secret(secret_id):
    secret_rec = Secret.query.filter_by(id=secret_id).one_or_none()
    if secret_rec is None:
        abort(404, "Secret not found")

    secret_rec.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


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

    # check secrets
    for job in schema['jobs']:
        for step in job['steps']:
            for field, value in step.items():
                if field in ['access-token', 'ssh-key']:
                    secret = Secret.query.filter_by(project=branch.project, name=value).one_or_none()
                    if secret is None:
                        abort(400, "Secret '%s' does not exists" % value)

    # TODO: check if git url is valid according to giturlparse
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


def update_stage(stage_id, data):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    if 'name' in data:
        stage.name = data['name']

    if 'description' in data:
        stage.description = data['description']

    if 'enabled' in data:
        stage.enabled = data['enabled']

    if 'schema_code' in data:
        _, schema = _check_and_correct_stage_schema(stage.branch, data, stage.schema_code)
        stage.schema = schema
        stage.schema_code = data['schema_code']
        flag_modified(stage, 'schema')
        if stage.triggers is None:
            stage.triggers = {}
        _prepare_new_planner_triggers(stage.id, schema['triggers'], stage.schema['triggers'], stage.triggers)
        flag_modified(stage, 'triggers')
        log.info('new schema: %s', stage.schema)

    db.session.commit()

    result = stage.get_json()
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


def get_executor(executor_id):
    ex = Executor.query.filter_by(id=executor_id).one_or_none()
    if ex is None:
        abort(400, "Cannot find executor with id %s" % executor_id)

    return ex.get_json(), 200


def get_executors(unauthorized=None, start=0, limit=10):
    q = Executor.query
    q = q.filter_by(deleted=None)
    if unauthorized:
        q = q.filter_by(authorized=False)
    else:
        q = q.filter_by(authorized=True)
    q = q.order_by(Executor.name)
    total = q.count()
    q = q.offset(start).limit(limit)
    executors = []
    for e in q.all():
        executors.append(e.get_json())
    return {'items': executors, 'total': total}, 200


def update_executors(executors):
    log.info('executors %s', executors)

    execs = []
    for e in executors:
        executor = Executor.query.filter_by(id=e['id']).one_or_none()
        if executor is None:
            abort(400, 'Cannot find executor %s' % e['id'])
        execs.append(executor)

    for data, executor in zip(executors, execs):
        if 'authorized' in data:
            executor.authorized = data['authorized']
    db.session.commit()

    return {}, 200


def update_executor(executor_id, data):
    executor = Executor.query.filter_by(id=executor_id).one_or_none()
    if executor is None:
        abort(404, "Executor not found")

    if 'groups' in data:
        # check new groups
        new_groups = set()
        if data['groups']:
            for g_id in data['groups']:
                g = ExecutorGroup.query.filter_by(id=g_id['id']).one_or_none()
                if g is None:
                    abort(404, "Executor Group with id %s not found" % g_id)
                new_groups.add(g)

        # get old groups
        current_groups = set()
        assignments_map = {}
        for ea in executor.executor_groups:
            current_groups.add(ea.executor_group)
            assignments_map[ea.executor_group.id] = ea

        # remove groups
        removed = current_groups - new_groups
        for r in removed:
            ea = assignments_map[r.id]
            db.session.delete(ea)

        # add groups
        added = new_groups - current_groups
        for a in added:
            ExecutorAssignment(executor=executor, executor_group=a)

    db.session.commit()

    return executor.get_json(), 200


def delete_executor(executor_id):
    executor = Executor.query.filter_by(id=executor_id).one_or_none()
    if executor is None:
        abort(404, "Executor not found")

    executor.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def get_group(group_id):
    eg = ExecutorGroup.query.filter_by(id=group_id).one_or_none()
    if eg is None:
        abort(400, "Cannot find executor group with id %s" % group_id)

    return eg.get_json(), 200


def get_groups(start=0, limit=10):
    q = ExecutorGroup.query
    q = q.filter_by(deleted=None)
    q = q.order_by(ExecutorGroup.name)
    total = q.count()
    q = q.offset(start).limit(limit)
    groups = []
    for eg in q.all():
        groups.append(eg.get_json())
    return {'items': groups, 'total': total}, 200


def create_group(group):
    group_rec = ExecutorGroup.query.filter_by(name=group['name']).one_or_none()
    if group_rec is not None:
        abort(400, "Group with name %s already exists" % group['name'])

    project = None
    if 'project_id' in group:
        project = Project.query.filter_by(id=group['project_id']).one_or_none()
        if project is None:
            abort(400, "Cannot find project with id %s" % group['project_id'])

    new_group = ExecutorGroup(name=group['name'], project=project)
    db.session.commit()

    return new_group.get_json(), 201


def update_group():
    pass


def delete_group():
    pass
