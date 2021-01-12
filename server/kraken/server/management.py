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

from flask import abort
from sqlalchemy.orm.attributes import flag_modified
import pytimeparse

from . import consts, srvcheck
from .models import db, Branch, Stage, Agent, AgentsGroup, Secret, AgentAssignment, Setting
from .models import Project, BranchSequence
from .schema import check_and_correct_stage_schema, SchemaError, execute_schema_code
from .schema import prepare_new_planner_triggers

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
    projects = []
    for p in q.all():
        projects.append(p.get_json(with_results=False))
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
    BranchSequence(branch=new_branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
    BranchSequence(branch=new_branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
    BranchSequence(branch=new_branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
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

    schema_code = None
    if 'schema_code' in stage:
        schema_code = stage['schema_code']

    try:
        schema_code, schema = check_and_correct_stage_schema(branch, stage['name'], schema_code)
    except SchemaError as e:
        abort(400, str(e))

    # create record
    new_stage = Stage(branch=branch, name=stage['name'], schema=schema, schema_code=schema_code)
    BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_RUN, value=0)
    BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
    BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
    db.session.flush()

    triggers = {}
    prepare_new_planner_triggers(new_stage.id, schema['triggers'], None, triggers)
    new_stage.triggers = triggers

    db.session.commit()

    return new_stage.get_json(), 201


def get_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    result = stage.get_json()
    return result, 200


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
        try:
            schema_code, schema = check_and_correct_stage_schema(stage.branch, data['name'], data['schema_code'])
        except SchemaError as e:
            abort(400, str(e))
        stage.schema = schema
        stage.schema_code = schema_code
        flag_modified(stage, 'schema')
        if stage.triggers is None:
            stage.triggers = {}
        prepare_new_planner_triggers(stage.id, schema['triggers'], stage.schema['triggers'], stage.triggers)
        flag_modified(stage, 'triggers')
        log.info('new schema: %s', stage.schema)

    db.session.commit()

    if 'schema_from_repo_enabled' in data:
        schema_from_repo_enabled = data['schema_from_repo_enabled']
    else:
        schema_from_repo_enabled = stage.schema_from_repo_enabled

    if schema_from_repo_enabled:
        if 'repo_url' in data:
            stage.repo_url = data['repo_url']
        if 'repo_branch' in data:
            stage.repo_branch = data['repo_branch']
        if 'repo_access_token' in data:
            stage.repo_access_token = data['repo_access_token']
        if 'schema_file' in data:
            stage.schema_file = data['schema_file']
        if 'repo_refresh_interval' in data:
            # check if interval can be parsed
            try:
                int(data['repo_refresh_interval'])
            except:
                int(pytimeparse.parse(data['repo_refresh_interval']))
            stage.repo_refresh_interval = data['repo_refresh_interval']
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
        log.info('refresh schema repo %s, bg processing: %s', schema, t)

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


def update_agents(agents):
    log.info('agents %s', agents)

    agents2 = []
    for a in agents:
        agent = Agent.query.filter_by(id=a['id']).one_or_none()
        if agent is None:
            abort(400, 'Cannot find agent %s' % a['id'])
        agents2.append(agent)

    for data, agent in zip(agents, agents2):
        if 'authorized' in data:
            agent.authorized = data['authorized']
    db.session.commit()

    return {}, 200


def update_agent(agent_id, data):
    agent = Agent.query.filter_by(id=agent_id).one_or_none()
    if agent is None:
        abort(404, "Agent not found")

    if 'groups' in data:
        # check new groups
        new_groups = set()
        if data['groups']:
            for g_id in data['groups']:
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

    if 'disabled' in data:
        agent.disabled = data['disabled']

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
    db.session.commit()

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


def create_group(group):
    group_rec = AgentsGroup.query.filter_by(name=group['name']).one_or_none()
    if group_rec is not None:
        abort(400, "Group with name %s already exists" % group['name'])

    project = None
    if 'project_id' in group:
        project = Project.query.filter_by(id=group['project_id']).one_or_none()
        if project is None:
            abort(400, "Cannot find project with id %s" % group['project_id'])

    new_group = AgentsGroup(name=group['name'], project=project)
    db.session.commit()

    return new_group.get_json(), 201


def update_group():
    pass


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


def update_settings(settings):
    settings_recs = Setting.query.filter_by().all()

    for group_name, group in settings.items():
        for name, val in group.items():
            for s in settings_recs:
                if s.group == group_name and s.name == name:
                    if s.val_type == 'password' and val == '':
                        continue
                    s.set_value(val)

    db.session.commit()

    groups, _ = get_settings()
    log.info('settings %s', groups)

    return groups, 200


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

    # check clickhouse
    # TODO

    # check postgresql
    pgsql_addr = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    pgsql_open = srvcheck.is_addr_open(pgsql_addr)
    diags['postgresql'] = {
        'name': 'PostgreSQL',
        'address': pgsql_addr,
        'open': pgsql_open
    }

    # check redis
    rds_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    rds_open = srvcheck.is_addr_open(rds_addr, 6379)
    diags['redis'] = {
        'name': 'Redis',
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

    return diags
