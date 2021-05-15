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
import logging
import datetime
import xmlrpc.client
from urllib.parse import urlparse

from flask import abort
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import joinedload
import pytimeparse
import clickhouse_driver

from . import consts, srvcheck
from .models import db, Branch, Stage, Agent, AgentsGroup, Secret, AgentAssignment, Setting
from .models import Project, BranchSequence
from .schema import check_and_correct_stage_schema, SchemaError, execute_schema_code
from .schema import prepare_new_planner_triggers
from .bg.clry import app as clryapp

log = logging.getLogger(__name__)


def create_project(body):
    project = Project.query.filter_by(name=body['name']).one_or_none()
    if project is not None:
        abort(400, "Project with name %s already exists" % body['name'])

    new_project = Project(name=body['name'], description=body.get('description', ''))
    db.session.commit()

    return new_project.get_json(), 201


def update_project(project_id, body):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(404, "Project not found")

    if 'webhooks' in body:
        project.webhooks = body['webhooks']

    db.session.commit()

    result = project.get_json()
    return result, 200


def get_project(project_id):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    return project.get_json(with_results=True), 200


def delete_project(project_id):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    project.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def get_projects():
    q = Project.query
    q = q.filter_by(deleted=None)
    q = q.options(joinedload('branches'),
                  joinedload('branches.project'),
                  joinedload('branches.ci_last_incomplete_flow'),
                  joinedload('branches.ci_last_incomplete_flow.runs'),
                  joinedload('branches.ci_last_completed_flow'),
                  joinedload('branches.ci_last_completed_flow.runs'),
                  joinedload('secrets'))

    projects = []
    for p in q.all():
        projects.append(p.get_json(with_last_results=True))
    return {'items': projects, 'total': len(projects)}, 200


def create_branch(project_id, body):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(404, "Project not found")

    branch = Branch(project=project, name=body['name'])
    BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
    BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
    BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
    db.session.commit()

    return branch.get_json(), 201


def update_branch(branch_id, body):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    if 'name' in body:
        branch.name = body['name']

    db.session.commit()

    result = branch.get_json()
    return result, 200


def get_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")
    return branch.get_json(with_cfg=True), 200


def delete_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(400, "Branch with id %s does not exist" % branch_id)

    branch.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def create_secret(project_id, body):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    if body['kind'] == 'ssh-key':
        kind = consts.SECRET_KIND_SSH_KEY
        data = dict(username=body['username'],
                    key=body['key'])
    elif body['kind'] == 'simple':
        kind = consts.SECRET_KIND_SIMPLE
        data = dict(secret=body['secret'])
    else:
        abort(400, "Wrong data")

    secret = Secret(project=project, name=body['name'], kind=kind, data=data)
    db.session.commit()

    return secret.get_json(), 201


def update_secret(secret_id, body):
    secret = Secret.query.filter_by(id=secret_id, deleted=None).one_or_none()
    if secret is None:
        abort(404, "Secret not found")

    if 'name' in body:
        old_name = secret.name
        secret.name = body['name']
        log.info('changed name from %s to %s', old_name, secret.name)

    if secret.kind == consts.SECRET_KIND_SIMPLE:
        if 'secret' in body and body['secret'] != '******':
            secret.data['secret'] = body['secret']
    elif secret.kind == consts.SECRET_KIND_SSH_KEY:
        if 'username' in body:
            secret.data['username'] = body['username']
        if 'key' in body and body['key'] != '******':
            secret.data['key'] = body['key']
    flag_modified(secret, 'data')

    db.session.commit()

    result = secret.get_json()
    return result, 200


def delete_secret(secret_id):
    secret = Secret.query.filter_by(id=secret_id, deleted=None).one_or_none()
    if secret is None:
        abort(404, "Secret not found")

    secret.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def create_stage(branch_id, body):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    schema_code = None
    if 'schema_code' in body:
        schema_code = body['schema_code']

    try:
        schema_code, schema = check_and_correct_stage_schema(branch, body['name'], schema_code)
    except SchemaError as e:
        abort(400, str(e))

    # create record
    stage = Stage(branch=branch, name=body['name'], schema=schema, schema_code=schema_code)
    BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_RUN, value=0)
    BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
    BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
    db.session.flush()

    triggers = {}
    prepare_new_planner_triggers(stage.id, schema['triggers'], None, triggers)
    stage.triggers = triggers

    db.session.commit()

    return stage.get_json(), 201


def get_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    result = stage.get_json()
    return result, 200


def update_stage(stage_id, body):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    if 'name' in body:
        stage.name = body['name']

    if 'description' in body:
        stage.description = body['description']

    if 'enabled' in body:
        stage.enabled = body['enabled']

    if 'schema_code' in body:
        prev_triggers = stage.schema['triggers']
        try:
            schema_code, schema = check_and_correct_stage_schema(stage.branch, body['name'], body['schema_code'])
        except SchemaError as e:
            abort(400, str(e))
        stage.schema = schema
        stage.schema_code = schema_code
        flag_modified(stage, 'schema')
        if stage.triggers is None:
            stage.triggers = {}
        prepare_new_planner_triggers(stage.id, schema['triggers'], prev_triggers, stage.triggers)
        flag_modified(stage, 'triggers')
        log.info('new schema: %s', stage.schema)

    db.session.commit()

    if 'schema_from_repo_enabled' in body:
        schema_from_repo_enabled = body['schema_from_repo_enabled']
    else:
        schema_from_repo_enabled = stage.schema_from_repo_enabled

    if schema_from_repo_enabled:
        if 'repo_url' in body:
            stage.repo_url = body['repo_url']
        if 'repo_branch' in body:
            stage.repo_branch = body['repo_branch']
        if 'repo_access_token' in body:
            stage.repo_access_token = body['repo_access_token']
        if 'schema_file' in body:
            stage.schema_file = body['schema_file']
        if 'repo_refresh_interval' in body:
            # check if interval can be parsed
            try:
                int(body['repo_refresh_interval'])
            except Exception:
                try:
                    int(pytimeparse.parse(body['repo_refresh_interval']))
                except Exception:
                    abort(400, 'Incorrect repo refresh interval value')
            stage.repo_refresh_interval = body['repo_refresh_interval']
            log.info('stage.repo_refresh_interval %s', stage.repo_refresh_interval)

        stage.repo_state = consts.REPO_STATE_REFRESHING
        stage.repo_error = ''
        db.session.commit()

        if stage.repo_refresh_job_id:
            planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
            planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)
            planner.remove_job(stage.repo_refresh_job_id)
            stage.repo_refresh_job_id = 0
            db.session.commit()

        from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
        t = bg_jobs.refresh_schema_repo.delay(stage.id)
        log.info('refresh schema repo %s, bg processing: %s', body, t)

    result = stage.get_json()
    return result, 200


def delete_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    stage.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def get_stage_schema_as_json(stage_id, body):
    schema_code = body
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    try:
        schema = execute_schema_code(stage.branch, schema_code['schema_code'])
    except Exception as e:
        return dict(stage_id=stage_id, error=str(e)), 200

    schema = json.dumps(schema, indent=4, separators=(',', ': '))

    return dict(stage_id=stage_id, schema=schema), 200

def get_stage_schedule(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    schedules = []

    if stage.triggers:
        planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
        planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)
        jobs = planner.get_jobs()
        jobs = {j['id']: j for j in jobs}

        for name, val in stage.triggers.items():
            if 'planner_job' not in name:
                continue
            if val not in jobs:
                continue
            job = jobs[val]
            s = dict(name=name,
                     job_id=val,
                     next_run_time=job['next_run_time'])
            schedules.append(s)

    return dict(schedules=schedules), 200

def get_agent(agent_id):
    ag = Agent.query.filter_by(id=agent_id).one_or_none()
    if ag is None:
        abort(400, "Cannot find agent with id %s" % agent_id)

    return ag.get_json(), 200


def get_agents(unauthorized=None, start=0, limit=10):
    q = Agent.query
    q = q.filter_by(deleted=None)
    if unauthorized:
        q = q.filter_by(authorized=False)
    else:
        q = q.filter_by(authorized=True)
    q = q.order_by(Agent.name)
    total = q.count()
    q = q.offset(start).limit(limit)
    agents = []
    for e in q.all():
        agents.append(e.get_json())
    return {'items': agents, 'total': total}, 200


def update_agents(body):
    agents = body
    log.info('agents %s', agents)

    agents2 = []
    for a in agents:
        agent = Agent.query.filter_by(id=a['id']).one_or_none()
        if agent is None:
            abort(400, 'Cannot find agent %s' % a['id'])
        agents2.append(agent)

    all_group = AgentsGroup.query.filter_by(name='all').one_or_none()

    for data, agent in zip(agents, agents2):
        if 'authorized' in data:
            agent.authorized = data['authorized']

            if agent.authorized and all_group:
                already_in = False
                for ag in agent.agents_groups:
                    if ag.agents_group_id == all_group.id:
                        already_in = True
                        break
                if not already_in:
                    AgentAssignment(agent=agent, agents_group=all_group)

    db.session.commit()

    return {}, 200


def update_agent(agent_id, body):
    agent = Agent.query.filter_by(id=agent_id).one_or_none()
    if agent is None:
        abort(404, "Agent not found")

    if 'groups' in body:
        # check new groups
        new_groups = set()
        if body['groups']:
            for g_id in body['groups']:
                g = AgentsGroup.query.filter_by(id=g_id['id']).one_or_none()
                if g is None:
                    abort(404, "Agents Group with id %s not found" % g_id)
                new_groups.add(g)

        # get old groups
        current_groups = set()
        assignments_map = {}
        for aa in agent.agents_groups:
            current_groups.add(aa.agents_group)
            assignments_map[aa.agents_group.id] = aa

        # remove groups
        removed = current_groups - new_groups
        for r in removed:
            aa = assignments_map[r.id]
            db.session.delete(aa)

        # add groups
        added = new_groups - current_groups
        for a in added:
            AgentAssignment(agent=agent, agents_group=a)

    if 'disabled' in body:
        agent.disabled = body['disabled']

    db.session.commit()

    return agent.get_json(), 200


def delete_agent(agent_id):
    agent = Agent.query.filter_by(id=agent_id).one_or_none()
    if agent is None:
        abort(404, "Agent not found")

    if agent.job is not None:
        job = agent.job
        job.agent = None
        job.state = consts.JOB_STATE_QUEUED
        agent.job = None

    agent.deleted = datetime.datetime.utcnow()
    agent.authorized = False
    agent.disabled = True
    db.session.commit()

    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    t = bg_jobs.destroy_machine.delay(agent.id)
    log.info('destroy machine with agent %s, bg processing: %s', agent.id, t)

    return {}, 200


def get_group(group_id):
    ag = AgentsGroup.query.filter_by(id=group_id).one_or_none()
    if ag is None:
        abort(400, "Cannot find agent group with id %s" % group_id)

    return ag.get_json(), 200


def get_groups(start=0, limit=10):
    q = AgentsGroup.query
    q = q.filter_by(deleted=None)
    q = q.order_by(AgentsGroup.name)
    total = q.count()
    q = q.offset(start).limit(limit)
    groups = []
    for ag in q.all():
        groups.append(ag.get_json())
    return {'items': groups, 'total': total}, 200


def create_group(body):
    group = AgentsGroup.query.filter_by(name=body['name']).one_or_none()
    if group is not None:
        abort(400, "Group with name %s already exists" % body['name'])

    project = None
    if 'project_id' in body:
        project = Project.query.filter_by(id=body['project_id']).one_or_none()
        if project is None:
            abort(400, "Cannot find project with id %s" % body['project_id'])

    group = AgentsGroup(name=body['name'], project=project)
    db.session.commit()

    return group.get_json(), 201


def update_group(group_id, body):
    group = AgentsGroup.query.filter_by(id=group_id).one_or_none()
    if group_id is None:
        abort(404, "Group not found")

    #if 'groups' in body:
    log.info('GROUP %s', body)

    if 'name' in body:
        group.name = body['name']

    if 'deployment' in body:
        # TODO: destroy resources connected with previous deployment
        group.deployment = body['deployment']

    db.session.commit()

    return group.get_json(), 200


def delete_group(group_id):
    group = AgentsGroup.query.filter_by(id=group_id).one_or_none()
    if group is None:
        abort(404, "Agents group with id %s not found" % group_id)

    group.deleted = datetime.datetime.utcnow()
    db.session.commit()

    return {}, 200


def get_settings():
    settings = Setting.query.filter_by().all()

    groups = {}
    for s in settings:
        if s.group not in groups:
            groups[s.group] = {}
        grp = groups[s.group]
        grp[s.name] = s.get_value()

    return groups, 200


def update_settings(body):
    settings = Setting.query.filter_by().all()

    for group_name, group in body.items():
        for name, val in group.items():
            for s in settings:
                if s.group == group_name and s.name == name:
                    if s.val_type == 'password' and val == '':
                        continue
                    s.set_value(val)

    db.session.commit()

    settings, _ = get_settings()
    return settings, 200


def get_branch_sequences(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    q = BranchSequence.query.filter_by(branch=branch)
    q = q.order_by(BranchSequence.id)

    seqs = []
    for bs in q.all():
        seqs.append(bs.get_json())

    return {'items': seqs, 'total': len(seqs)}, 200


def get_diagnostics():
    diags = {}

    # check postgresql
    pgsql_addr = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    pgsql_open = srvcheck.is_addr_open(pgsql_addr)
    diags['postgresql'] = {
        'name': 'PostgreSQL',
        'address': pgsql_addr,
        'open': pgsql_open
    }

    # check clickhouse
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    ch_open = srvcheck.is_addr_open(ch_url)
    diags['clickhouse'] = {
        'name': 'ClickHouse',
        'address': ch_url,
        'open': ch_open
    }

    # check redis
    rds_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    rds_open = srvcheck.is_addr_open(rds_addr, 6379)
    diags['redis'] = {
        'name': 'Redis',
        'address': rds_addr,
        'open': rds_open
    }

    # check planner
    plnr_addr = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    plnr_open = srvcheck.is_addr_open(plnr_addr)
    diags['planner'] = {
        'name': 'Kraken Planner',
        'address': plnr_addr,
        'open': plnr_open
    }

    # celery overview
    diags['celery'] = {
        'name': 'Celery',
        'address': '',
        'open': True,
    }

    # get current celery tasks
    with clryapp.pool.acquire(block=True) as conn:
        tasks = conn.default_channel.client.lrange('celery', 0, -1)
    diags['celery']['current_tasks'] = []
    for task in tasks:
        t = json.loads(task)
        diags['celery']['current_tasks'].append(t)

    # get the last celery tasks
    if ch_open:
        o = urlparse(ch_url)
        ch = clickhouse_driver.Client(host=o.hostname)

        now = datetime.datetime.utcnow()
        start_date = now - datetime.timedelta(hours=1112)
        query = "select max(time) as mt, tool, count(*) from logs "
        query += "where service = 'celery' and tool != '' "
        query += "group by tool "
        query += "having mt > %(start_date)s "
        query += "order by mt desc "
        query += "limit 100;"
        resp = ch.execute(query, {'start_date': start_date})
        diags['celery']['last_tasks'] = resp
    else:
        diags['celery']['last_tasks'] = []

    return diags


def  get_celery_logs(task_name):
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    query = "select time,message from logs where service = 'celery' and tool = %(task_name)s order by time desc, seq desc limit 1000;"
    rows = ch.execute(query, {'task_name': task_name})

    logs = []
    for r in reversed(rows):
        entry = dict(time=r[0],
                     message=r[1])
        logs.append(entry)

    return {'items': logs, 'total': len(logs)}, 200


def  get_services_logs(services):
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    query = "select time,message,service,host,level,tool from logs "
    where = []
    params = {}
    for idx, s in enumerate(services):
        param = 'service%d' % idx
        if '/' in s:
            s, t = s.split('/')
            tparam = 'tool%d' % idx
            where.append("(service = %%(%s)s and tool = %%(%s)s)" % (param, tparam))
            params[param] = s
            params[tparam] = t
        else:
            where.append("service = %%(%s)s" % param)
            params[param] = s
    if where:
        where = " or ".join(where)
        query += "where " + where + " "
    query += "order by time desc, seq desc limit 1000"
    rows = ch.execute(query, params)

    logs = []
    for r in reversed(rows):
        entry = dict(time=r[0],
                     message=r[1],
                     service=r[2],
                     host=r[3],
                     level=r[4],
                     tool=r[5])
        logs.append(entry)

    return {'items': logs, 'total': len(logs)}, 200
