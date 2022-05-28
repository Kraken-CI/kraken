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

import io
import os
import re
import json
import logging
import datetime
import xmlrpc.client
from urllib.parse import urlparse

from flask import abort
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import asc, desc, extract
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
import pytimeparse
import clickhouse_driver
import redis
import boto3
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.compute import ComputeManagementClient

from . import consts, srvcheck, kkrq
from .models import db, Branch, Stage, Agent, AgentsGroup, Secret, AgentAssignment, Setting
from .models import Project, BranchSequence, System, Flow, duration_to_txt
from .models import Tool
from .schema import check_and_correct_stage_schema, SchemaError, execute_schema_code
from .schema import prepare_new_planner_triggers
from .cloud import aws, azure, k8s
from ..version import version as server_version
from . import notify
from . import utils
from . import minioops
from . import schemaval


log = logging.getLogger(__name__)


def create_project(body):
    if 'name' not in body:
        abort(400, "Missing name in project")
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


def get_project(project_id, with_results):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    return project.get_json(with_results=with_results), 200


def delete_project(project_id):
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        abort(400, "Project with id %s does not exist" % project_id)

    project.deleted = utils.utcnow()
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

    if 'id' in body:
        parent_branch = Branch.query.filter_by(id=body['id']).one_or_none()
        if parent_branch is None:
            abort(404, "Branch not found")
    else:
        parent_branch = None


    if 'branch_name' in body and body['branch_name']:
        branch_name = body['branch_name']
    else:
        branch_name = body['name']

    branch = Branch(project=project, name=body['name'], branch_name=branch_name)

    if parent_branch:
        if body['forking_model'] == 'model-1':
            # forked branch continues numbering, old branch resets numbering
            for bs in parent_branch.sequences:
                if bs.stage is not None:
                    continue
                BranchSequence(branch=branch, kind=bs.kind, value=bs.value)
                bs.value = 0
        else:
            # forked branch resets numbering, old branch continues numbering
            BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
            BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
            BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)

        db.session.commit()

        # clone stages
        for stage in parent_branch.stages:
            if stage.deleted:
                continue
            new_stage = Stage(
                name=stage.name,
                description=stage.description,
                branch=branch,
                enabled=stage.enabled,
                schema=stage.schema,
                schema_code=stage.schema_code,
                timeouts=stage.timeouts,
                repo_access_token=stage.repo_access_token,
                repo_branch=stage.repo_branch,
                repo_url=stage.repo_url,
                schema_file=stage.schema_file,
                schema_from_repo_enabled=stage.schema_from_repo_enabled,
                repo_refresh_interval=stage.repo_refresh_interval,
                git_clone_params=stage.git_clone_params)

            if body['forking_model'] == 'model-1':
                # forked branch continues numbering, old branch resets numbering
                for bs in stage.sequences:
                    BranchSequence(branch=branch, stage=new_stage, kind=bs.kind, value=bs.value)
                    bs.value = 0
            else:
                # forked branch resets numbering, old branch continues numbering
                BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_RUN, value=0)
                BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
                BranchSequence(branch=branch, stage=new_stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)

            db.session.flush()

            triggers = {}
            prepare_new_planner_triggers(new_stage.id, new_stage.schema['triggers'], None, triggers)
            stage.triggers = triggers

            db.session.commit()
    else:
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

    if 'branch_name' in body:
        branch.branch_name = body['branch_name']

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

    branch.deleted = utils.utcnow()
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

    secret.deleted = utils.utcnow()
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

    if 'schema_from_repo_enabled' in body:
        schema_from_repo_enabled = body['schema_from_repo_enabled']
    else:
        schema_from_repo_enabled = stage.schema_from_repo_enabled

    stage.schema_from_repo_enabled = schema_from_repo_enabled
    db.session.commit()

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
        if 'git_clone_params' in body:
            stage.git_clone_params = body['git_clone_params']

        stage.repo_state = consts.REPO_STATE_REFRESHING
        stage.repo_error = ''
        db.session.commit()

        if stage.repo_refresh_job_id:
            planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
            planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)
            planner.remove_job(stage.repo_refresh_job_id)
            stage.repo_refresh_job_id = ''
            db.session.commit()

        from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
        kkrq.enq_neck(bg_jobs.refresh_schema_repo, stage.id, 0, ignore_args=[1])

    result = stage.get_json()

    return result, 200


def delete_stage(stage_id):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    stage.deleted = utils.utcnow()
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


def get_agents(unauthorized=None, start=0, limit=10, sort_field="name", sort_dir="asc"):
    q = Agent.query
    q = q.filter_by(deleted=None)
    if unauthorized:
        q = q.filter_by(authorized=False)
    else:
        q = q.filter_by(authorized=True)

    total = q.count()

    # sorting
    sort_func = asc
    if sort_dir == "desc":
        sort_func = desc

    if sort_field in ['last_seen', 'ip_address', 'name', 'address', 'id']:
        q = q.order_by(sort_func(sort_field))
    else:
        q = q.order_by(Agent.name)

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

    # only mark as deleted, do not unassign from groups yet as it is needed
    # in destroy_machine if it is cloud machine
    agent.deleted = utils.utcnow()
    agent.authorized = False
    agent.disabled = True
    db.session.commit()

    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    kkrq.enq(bg_jobs.destroy_machine, agent.id)

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

    group.deleted = utils.utcnow()
    db.session.commit()

    return {}, 200


def get_aws_ec2_regions():
    credential = aws.login_to_aws()
    if not credential:
        abort(500, "Incorrect AWS credential, set them in global cloud settings")
    ec2 = boto3.client('ec2', region_name='us-east-1', **credential)
    resp = ec2.describe_regions()
    return {'items': resp['Regions'], 'total': len(resp['Regions'])}, 200


def get_aws_ec2_instance_types(region):
    credential = aws.login_to_aws()
    if not credential:
        abort(500, "Incorrect AWS credential, set them in global cloud settings")
    ec2 = boto3.client('ec2', region_name=region, **credential)
    resp = ec2.describe_instance_type_offerings(Filters=[{'Name': 'location', 'Values':[region]}])
    types = resp['InstanceTypeOfferings']
    types.sort(key=lambda x: x['InstanceType'])
    return {'items': types, 'total': len(types)}, 200


def get_azure_locations():
    # Acquire a credential object using service principal authentication.
    credential, subscription_id = azure.login_to_azure()
    if not credential:
        abort(500, "Incorrect Azure credential, set them in global cloud settings")
    subscription_client = SubscriptionClient(credential)
    locations = subscription_client.subscriptions.list_locations(subscription_id)
    locs = []
    for location in locations:
        locs.append(location.name)
    locs.sort()

    return {'items': locs, 'total': len(locs)}, 200


def get_azure_vm_sizes(location):
    # Acquire a credential object using service principal authentication.
    credential, subscription_id = azure.login_to_azure()
    if not credential:
        abort(500, "Incorrect Azure credential, set them in global cloud settings")
    compute_client = ComputeManagementClient(credential, subscription_id)
    vm_sizes_list = compute_client.virtual_machine_sizes.list(location=location)
    vm_sizes = []
    for s in vm_sizes_list:
        vm_sizes.append(s.as_dict())
    vm_sizes.sort(key=lambda x: x['name'])

    return {'items': vm_sizes, 'total': len(vm_sizes)}, 200

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
    pgsql_open = srvcheck.is_service_open(pgsql_addr)
    diags['postgresql'] = {
        'name': 'PostgreSQL',
        'address': pgsql_addr,
        'open': pgsql_open
    }

    # check clickhouse
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    ch_open = srvcheck.is_service_open(ch_url)
    diags['clickhouse'] = {
        'name': 'ClickHouse',
        'address': ch_url,
        'open': ch_open
    }

    # check redis
    rds_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    rds_open = srvcheck.is_service_open(rds_addr, 6379)
    diags['redis'] = {
        'name': 'Redis',
        'address': rds_addr,
        'open': rds_open
    }

    # check minio
    minio_addr, _, _ = minioops.get_minio_addr()
    minio_open = srvcheck.is_service_open(minio_addr)
    if minio_open:
        minio_open = minioops.check_connection()
    diags['minio'] = {
        'name': 'MinIO',
        'address': minio_addr,
        'open': minio_open
    }

    # check planner
    plnr_addr = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    plnr_open = srvcheck.is_service_open(plnr_addr)
    diags['planner'] = {
        'name': 'Kraken Planner',
        'address': plnr_addr,
        'open': plnr_open
    }

    # rq overview
    diags['rq'] = {
        'name': 'RQ',
        'address': '',
        'open': True,
    }

    # get current RQ jobs
    now = datetime.datetime.now()
    week_ago = now - datetime.timedelta(days=7)
    all_jobs = kkrq.get_jobs()
    for jobs, name in zip(all_jobs, ['scheduled', 'current', 'finished', 'failed', 'deferred']):
        jobs2 = []
        for job in jobs:
            if job.ended_at and job.ended_at < week_ago:
                continue
            job = dict(id=job.id,
                       created_at=job.created_at,
                       ended_at=job.ended_at,
                       enqueued_at=job.enqueued_at,
                       func_name=job.func_name,
                       description=job.description,
                       status=job.get_status(refresh=False))
            jobs2.append(job)
        key = '%s_jobs' % name
        diags['rq'][key] = jobs2

    return diags


def get_last_rq_jobs_names():
    # get the last RQ jobs
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    now = utils.utcnow()
    start_date = now - datetime.timedelta(hours=12111)
    query = "select max(time) as mt, tool, count(*) from logs "
    query += "where service = 'rq' and tool != '' "
    query += "group by tool "
    query += "having mt > %(start_date)s "
    query += "order by mt desc "
    query += "limit 100;"
    resp = ch.execute(query, {'start_date': start_date})
    task_names = []
    for row in resp:
        task_names.append(dict(time=row[0], name=row[1], lines=row[2]))

    return {'items': task_names}, 200


def  get_services_logs(services, level=None):
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    query = "select time,message,service,host,level,tool from logs "
    where = []
    params = {}
    for idx, s in enumerate(services):
        if s == 'all':
            continue
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
        where = "where (" + where + ") "
    if level:
        level = level.upper()
        if level == 'ERROR':
            lq = "level = 'ERROR'"
        elif level == 'WARNING':
            lq = "level in ('WARNING', 'ERROR')"
        else:
            lq = "level in ('INFO', 'WARNING', 'ERROR')"
        if where:
            where += "and %s " % lq
        else:
            where = "where %s " % lq
    if where:
        query += where
    query += " order by time desc, seq desc limit 1000"
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


def get_errors_in_logs_count():
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_KRAKEN_DB)

    errors_count = rds.get('error-logs-count')
    if errors_count:
        errors_count = int(errors_count)
    else:
        errors_count = 0

    return {'errors_count': errors_count}, 200


def get_settings_working_state(resource):
    if resource == 'email':
        state = notify.check_email_settings()
    elif resource == 'slack':
        state = notify.check_slack_settings()
    elif resource == 'aws':
        state = aws.check_aws_settings()
    elif resource == 'azure':
        state = azure.check_azure_settings()
    elif resource == 'kubernetes':
        state = k8s.check_k8s_settings()
    else:
        abort(400, "Unsupported resource type: %s" % resource)

    return {'state': state}, 200


def get_systems():
    q = System.query
    q = q.order_by(System.name)

    systems = []
    for s in q.all():
        systems.append(s.get_json())
    return {'items': systems, 'total': len(systems)}, 200


def move_branch(branch_id, body):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    proj_id = body.get('project_id', None)
    if proj_id is None:
        abort(400, "Missing project id")

    proj = Project.query.filter_by(id=proj_id).one_or_none()
    if proj is None:
        abort(400, "Project with id %s does not exist" % proj_id)

    branch.project_id = proj.id
    db.session.commit()

    return branch.get_json(with_cfg=True), 200


def get_branch_stats(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    resp = {
        'id': branch.id,
        'ci': {},
        'dev': {},
    }

    today = utils.utcnow()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    for kind, rsp in [(consts.FLOW_KIND_CI, resp['ci']), (consts.FLOW_KIND_DEV, resp['dev'])]:
        q = Flow.query.filter_by(branch=branch, kind=kind)

        # total stats
        rsp['flows_total'] = q.count()
        rsp['flows_last_month'] = q.filter(Flow.created >= month_ago).count()
        rsp['flows_last_week'] = q.filter(Flow.created >= week_ago).count()

        # duration stats
        rsp['avg_duration_last_month'] = None
        rsp['avg_duration_last_week'] = None
        rsp['durations'] = []
        if rsp['flows_last_month'] > 0:
            q2 = q.filter(Flow.finished.is_not(None))
            q2 = q2.with_entities(func.avg(extract('epoch', Flow.finished) - extract('epoch', Flow.created)).label('average'))
            secs = q2.filter(Flow.created >= month_ago).all()[0][0]
            dur = datetime.timedelta(seconds=secs)
            rsp['avg_duration_last_month'] = duration_to_txt(dur)
            if rsp['flows_last_week'] > 0:
                secs = q2.filter(Flow.created >= week_ago).all()[0][0]
                if secs:
                    dur = datetime.timedelta(seconds=secs)
                    rsp['avg_duration_last_week'] = duration_to_txt(dur)

            # durations table
            q2 = q.with_entities(Flow.id, Flow.label, extract('epoch', Flow.finished) - extract('epoch', Flow.created))
            q2 = q2.order_by(asc(Flow.created))
            durs = []
            for f_id, f_label, f_dur in q2.all():
                durs.append(dict(flow_label=f_label if f_label else ("%d." % f_id),
                                 duration=None if f_dur is None else int(f_dur)))
            rsp['durations'] = durs

    return resp, 200


def get_workflow_schema():
    return schemaval.get_schema(), 200


def get_tools(start=0, limit=30, sort_field="name", sort_dir="asc"):
    q = Tool.query
    q = q.filter_by(deleted=None)

    total = q.count()

    sort_func = asc
    if sort_dir == "desc":
        sort_func = desc

    if sort_field in ['location', 'entry', 'name', 'version', 'id']:
        q = q.order_by(sort_func(sort_field))
    else:
        q = q.order_by(Tool.name)

    q = q.order_by(asc(Tool.created))

    q = q.offset(start).limit(limit)

    tools = []
    for t in q.all():
        tools.append(t.get_json(with_details=True))
    return {'items': tools, 'total': total}, 200


def _create_or_update_tool(meta):
    name = meta['name']
    description = meta['description']
    location = meta['location']
    entry = meta['entry']
    fields = meta['parameters']
    version = meta.get('version', None)

    tool = None
    if version:
        # find tool to overwrite
        q = Tool.query
        q = q.filter_by(name=name)
        q = q.filter_by(version=version)
        q = q.filter_by(deleted=None)
        tool = q.one_or_none()
    else:
        # fint the latest tool to estimate next version
        q = Tool.query
        q = q.filter_by(name=name)
        q = q.filter_by(deleted=None)
        q = q.order_by(desc(Tool.created))
        tools = q.all()
        prev_tool = None
        for t in tools:
            if t.version[-1].isdigit():
                prev_tool = t
                break

    if not version:
        if not prev_tool:
            version = '1'
        else:
            m = re.match('^(.*)(\d+)$', prev_tool.version)
            if not m:
                version = '1'
            else:
                ver_base = m.group(1)
                ver_num = int(m.group(2))
                ver_num += 1
                version = '%s%d' % (ver_base, ver_num)

    if tool:
        tool.description = description
        tool.version = version
        tool.location=location
        tool.entry = entry
        tool.fields = fields
    else:
        tool = Tool(name=name, description=description, version=version, location=location, entry=entry, fields=fields)

    return tool


def create_or_update_tool(body):
    _create_or_update_tool(body)
    db.session.commit()

    return tool.get_json(), 201


def upload_new_or_overwrite_tool(name, body, file=None):
    meta = body['meta']
    if name != meta['name']:
        msg = 'Name in description (%s) does not match name in url (%s)' % (meta['name'], name)
        abort(400, msg)

    tool = _create_or_update_tool(meta)
    db.session.flush()

    bucket, mc = minioops.get_or_create_minio_bucket_for_tool(tool.id)
    dest = '%s/tool.zip' % tool.version

    mc.put_object(bucket, dest, file.stream, -1, part_size=10*1024*1024, content_type="application/zip")

    tool.location = 'minio:%s/%s' % (bucket, dest)
    db.session.commit()

    return tool.get_json(), 201


def get_server_version():
    return {'version': server_version}, 200
