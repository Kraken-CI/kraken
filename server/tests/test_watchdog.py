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
import datetime
from unittest.mock import patch

import pytest

from kraken.server import consts, utils, initdb
from kraken.server.models import db, Run, Job, Branch, Flow, Stage, Project, System, AgentsGroup
from kraken.server.models import AgentAssignment, Agent

from common import create_app

from kraken.server import watchdog

log = logging.getLogger(__name__)


@pytest.mark.db
def test__check_agents_to_destroy():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        # define aws credentials
        # TODO
        #db.session.commit()

        # empty db, no records
        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 0
        assert outdated_count == 0
        assert dangling_count == 0

        # simple case but still empty
        a = Agent(name='agent', address='1.2.3.4', authorized=True, extra_attrs=dict(instance_id=1))
        ag = AgentsGroup(name='group')
        AgentAssignment(agent=a, agents_group=ag)
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 0
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with empty deployment
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws={})
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # CHECK _destroy_and_delete_if_outdated

        # with deployment and destruction_after_time=0
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=0))
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with deployment and destruction_after_time=0 and destruction_after_jobs=0
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=0, destruction_after_jobs=0))
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with deployment and destruction_after_time > 0 but no jobs
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=10, destruction_after_jobs=0))
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with deployment and destruction_after_time > 0 and with some job but just finished
        now = utils.utcnow()
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=10, destruction_after_jobs=0))
        project = Project()
        sys = System()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch)
        run = Run(stage=stage, flow=flow, reason='abc')
        job = Job(run=run, system=sys, agents_group=ag, agent_used=a)
        job.finished = now
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with deployment and destruction_after_time > 0 and with a job finished as needed
        job.finished = now - datetime.timedelta(seconds=60 * 11)
        a.created = now - datetime.timedelta(seconds=60 * 12)
        db.session.commit()

        with patch('kraken.server.kkrq.enq'):
            all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 1
        assert dangling_count == 0
        assert a.disabled

        # with deployment and destruction_after_jobs > 0 but with a job just finished
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=0, destruction_after_jobs=1))
        job.finished = now
        job.state = consts.JOB_STATE_ASSIGNED
        a.disabled = False
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # with deployment and destruction_after_jobs > 0 but with a job finished
        job.state = consts.JOB_STATE_COMPLETED
        db.session.commit()

        with patch('kraken.server.kkrq.enq'):
            all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 1
        assert dangling_count == 0
        assert a.disabled

        # RESET

        # with deployment and no destruction_after_time and no destruction_after_jobs
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(destruction_after_time=0, destruction_after_jobs=0))
        a.disabled = False
        db.session.commit()

        all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 0
        assert not a.disabled

        # CHECK _delete_if_missing_in_aws

        # with deployment and agent with AWS instance
        ag.deployment = dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2, aws=dict(region='region'))
        db.session.commit()

        with patch('kraken.server.cloud.aws_ec2.vm_exists', return_value=False):
            all_count, outdated_count, dangling_count = watchdog._check_agents_to_destroy()
        assert all_count == 1
        assert outdated_count == 0
        assert dangling_count == 1
        assert a.disabled
