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

from sqlalchemy.orm.attributes import flag_modified

from kraken.server import consts, initdb, access, utils
from kraken.server.models import db, Run, Job, Step, Branch, Flow, Stage, Project, System, Tool, AgentsGroup, Agent, BranchSequence
from kraken.server import exec_utils

from common import create_app, prepare_user, check_missing_tests_in_mod

# TODO
# def test_missing_tests():
#     check_missing_tests_in_mod(backend, __name__)


@pytest.mark.db
def test_evaluate_step_fields():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        #access.init()
        #_, token_info = prepare_user()

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
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'abc': 'def'})
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        job = Job(run=run, agents_group=agents_group, system=system)
        step = Step(job=job, index=0, tool=tool, fields={}, fields_raw={'tool': 'shell', 'tool_location': '/'})
        agent = Agent(name='a1', address='1.2.3.4')
        agent.job = job
        job.agent_used = agent
        db.session.commit()

        step.fields_raw['cmd'] = 'echo #{flow.data.abc}'
        flag_modified(step, 'fields_raw')
        db.session.commit()

        exec_utils.evaluate_step_fields(step)

        assert step.fields == {'cmd': 'echo def', 'tool_location': '/', 'when': 'True'}
