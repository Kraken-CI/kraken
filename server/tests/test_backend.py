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

import os
import json
import logging
from unittest.mock import patch

import pytest
from hamcrest import assert_that, has_entries, matches_regexp, contains_exactly, instance_of

from kraken.server import consts, initdb, access, utils
from kraken.server.models import db, Run, Job, Step, Branch, Flow, Stage, Project, System, Tool, AgentsGroup, Agent, BranchSequence
from kraken.server import backend

from common import create_app, prepare_user, check_missing_tests_in_mod

# TODO
# def test_missing_tests():
#     check_missing_tests_in_mod(backend, __name__)


@pytest.mark.db
def test__handle_get_job_step():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        #access.init()
        #_, token_info = prepare_user()

        os.environ['MINIO_ROOT_USER'] = 'UFSEHRCFU4ACUEWHCHWU'
        os.environ['MINIO_ROOT_PASSWORD'] = 'HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY'

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={
            "parent": "Tarball",
            "triggers": {
                "parent": True
            },
            "parameters": [],
            "configs": [],
            "jobs": [],
            "notification": {}
        })
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        job = Job(run=run, agents_group=agents_group, system=system)
        step = Step(job=job, index=3, tool=tool, fields={}, fields_raw={'tool': 'shell', 'tool_location': '/'})
        agent = Agent(name='a1', address='1.2.3.4')
        agent.job = job
        job.agent_used = agent
        db.session.commit()

        result = backend._handle_get_job_step(agent)

        del os.environ['MINIO_ROOT_USER']
        del os.environ['MINIO_ROOT_PASSWORD']

        assert result == {
            'job_step': {'branch_id': branch.id,
                         'finish': False,
                         'flow_id': flow.id,
                         'flow_kind': 0,
                         'id': step.id,
                         'index': step.index,
                         'job_id': job.id,
                         'name': None,
                         'result': None,
                         'run_id': run.id,
                         'secrets': [],
                         'status': None,
                         'tool': None,
                         'tool_entry': None,
                         'tool_id': tool.id,
                         'tool_location': '/',
                         'tool_version': None},
        }


@pytest.mark.db
def test__handle_get_job2():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        #access.init()
        #_, token_info = prepare_user()

        os.environ['MINIO_ROOT_USER'] = 'UFSEHRCFU4ACUEWHCHWU'
        os.environ['MINIO_ROOT_PASSWORD'] = 'HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY'

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={
            "parent": "Tarball",
            "triggers": {
                "parent": True
            },
            "parameters": [],
            "configs": [],
            "jobs": [],
            "notification": {}
        })
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        job = Job(run=run, agents_group=agents_group, system=system, assigned=utils.utcnow(), timeout=1234, state=consts.JOB_STATE_QUEUED)
        step = Step(job=job, index=3, tool=tool, fields={}, fields_raw={'tool': 'shell', 'tool_location': '/'})
        agent = Agent(name='a1', address='1.2.3.4')
        agent.job = job
        job.agent_used = agent
        db.session.commit()

        result = backend._handle_get_job2(agent)

        del os.environ['MINIO_ROOT_USER']
        del os.environ['MINIO_ROOT_PASSWORD']

        assert_that(result, has_entries({
            'job': has_entries({
                'agent_id': agent.id,
                'agent_name': 'a1',
                'agents_group_id': agents_group.id,
                'agents_group_name': None,
                'branch_id': branch.id,
                'completed': None,
                'completion_status': None,
                'covered': False,
                # 'created': '2023-07-01T07:09:25Z',
                'deleted': None,
                'duration': '',
                'executor': None,
                'finished': None,
                'flow_id': flow.id,
                'flow_kind': flow.kind,
                'id': job.id,
                'name': None,
                'notes': None,
                'run_id': run.id,
                'secrets': [],
                'started': None,
                'state': consts.JOB_STATE_QUEUED,
                'system': None,
                'system_id': system.id,
                'timeout': 1110
            })
        }))

        assert job.started
        assert job.state == consts.JOB_STATE_ASSIGNED
