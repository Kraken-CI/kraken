# Copyright 2021 The Kraken Authors
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
#from unittest.mock import patch

import pytest

from kraken.server import utils, initdb
from kraken.server.models import db, Run, Job, Branch, Flow, Stage, Project, System, AgentsGroup
from kraken.server.models import AgentAssignment, Agent

from common import create_app

from kraken.server import scheduler

log = logging.getLogger(__name__)


@pytest.mark.db
def test__get_idle_agents_check_availability():
    app = create_app()

    now = utils.utcnow()

    with app.app_context():
        initdb._prepare_initial_preferences()

        # empty
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # agent but not authorized, etc
        a = Agent(name='agent', address='1.2.3.4', authorized=False, disabled=True, deleted=now)
        ag = AgentsGroup(name='group')
        AgentAssignment(agent=a, agents_group=ag)

        project = Project()
        sys = System()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch)
        run = Run(stage=stage, flow=flow, reason='abc')
        job = Job(run=run, system=sys, agents_group=ag, agent_used=a)

        db.session.commit()

        # not available yet
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # fully available
        a.authorized = True
        a.disabled = False
        a.deleted = None
        a.job = None
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 1

        # unauthorize
        a.authorized = False  # this causes that agent is unavailable
        a.disabled = False
        a.deleted = None
        a.job = None
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # disable
        a.authorized = True
        a.disabled = True  # this causes that agent is unavailable
        a.deleted = None
        a.job = None
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # delete
        a.authorized = True
        a.disabled = False
        a.deleted = now  # this causes that agent is unavailable
        a.job = None
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # busy
        a.authorized = True
        a.disabled = False
        a.deleted = None
        a.job = job  # this causes that agent is unavailable
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # available again
        a.authorized = True
        a.disabled = False
        a.deleted = None
        a.job = None
        db.session.commit()

        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 1


@pytest.mark.db
def test__get_idle_agents_groupped():
    app = create_app()

    now = utils.utcnow()

    with app.app_context():
        initdb._prepare_initial_preferences()

        # empty
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 0

        # agent but not authorized, etc
        a = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        ag = AgentsGroup(name='group')
        AgentAssignment(agent=a, agents_group=ag)

        db.session.commit()

        # available
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 1
        assert by_grp == {ag.id: [a]}
        assert by_sys_grp == {(ag.id, 'fake'): [a]}

        # sys grp with another system
        a.host_info = {'system': 'abc'}
        db.session.commit()
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 1
        assert by_grp == {ag.id: [a]}
        assert by_sys_grp == {(ag.id, 'abc'): [a]}

        # 1 agent in 2 groups
        ag2 = AgentsGroup(name='group2')
        AgentAssignment(agent=a, agents_group=ag2)
        db.session.commit()
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 1
        assert by_grp == {ag.id: [a], ag2.id: [a]}
        assert by_sys_grp == {(ag.id, 'abc'): [a],
                              (ag2.id, 'abc'): [a]}


        # added another agent and group
        a3 = Agent(name='agent3', address='1.2.3.6', authorized=True, disabled=False)
        ag3 = AgentsGroup(name='group3')
        AgentAssignment(agent=a3, agents_group=ag3)
        db.session.commit()
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 2
        assert by_grp == {ag.id: [a],
                          ag2.id: [a],
                          ag3.id: [a3]}
        assert by_sys_grp == {(ag.id, 'abc'): [a],
                              (ag2.id, 'abc'): [a],
                              (ag3.id, 'fake'): [a3]}

        # added agent3 to some old group
        AgentAssignment(agent=a3, agents_group=ag2)
        db.session.commit()
        count, by_grp, by_sys_grp = scheduler._get_idle_agents()
        assert count == 2
        assert by_grp == {ag.id: [a],
                          ag2.id: [a, a3],
                          ag3.id: [a3]}
        assert by_sys_grp == {(ag.id, 'abc'): [a],
                              (ag2.id, 'abc'): [a],
                              (ag2.id, 'fake'): [a3],
                              (ag3.id, 'fake'): [a3]}
