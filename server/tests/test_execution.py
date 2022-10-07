# Copyright 2022 The Kraken Authors
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
from unittest.mock import patch

import pytest

from kraken.server import consts, initdb, access
from kraken.server.models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, System, AgentsGroup, Agent, TestCase, Tool, BranchSequence
from kraken.server import results, execution

from common import create_app, prepare_user, check_missing_tests_in_mod

log = logging.getLogger(__name__)


def test_missing_tests():
    check_missing_tests_in_mod(execution, __name__)


@pytest.mark.db
def test_create_flow():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        db.session.commit()

        execution.create_flow(branch.id, 'dev', {}, token_info=token_info)


@pytest.mark.db
def test_get_flows():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        db.session.commit()

        execution.get_flows(branch.id, 'dev', token_info=token_info)


@pytest.mark.db
def test_get_flow():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        db.session.commit()

        execution.get_flow(flow.id, token_info=token_info)


@pytest.mark.db
def test_get_flow_runs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        db.session.commit()

        execution.get_flow_runs(flow.id, token_info=token_info)


@pytest.mark.db
def test_get_flow_artifacts():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        db.session.commit()

        execution.get_flow_artifacts(flow.id, token_info=token_info)


@pytest.mark.db
def atest_create_run():  # TODO
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

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
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        db.session.commit()

        body = dict(stage_id=stage.id)
        execution.create_run(flow.id, body, token_info=token_info)


@pytest.mark.db
def atest_run_run_jobs():  # TODO
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

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
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        db.session.commit()

        execution.run_run_jobs(run.id, token_info=token_info)


@pytest.mark.db
def test_job_rerun():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

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
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system)
        db.session.commit()

        execution.job_rerun(job.id, token_info=token_info)


@pytest.mark.db
def test_create_job():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

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
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_CI_FLOW, value=0)
        BranchSequence(branch=branch, kind=consts.BRANCH_SEQ_DEV_FLOW, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_CI_RUN, value=0)
        BranchSequence(branch=branch, stage=stage, kind=consts.BRANCH_SEQ_DEV_RUN, value=0)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        system = System()
        agents_group = AgentsGroup()
        db.session.commit()

        job = dict(run=run.id)
        execution.create_job(job, token_info=token_info)


@pytest.mark.db
def test_get_runs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason=dict(reason='manual'))
        db.session.commit()

        execution.get_runs(stage.id, token_info=token_info)


@pytest.mark.db
def test_get_run_jobs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason=dict(reason='manual'))
        db.session.commit()

        execution.get_run_jobs(run.id, token_info=token_info)


@pytest.mark.db
def test_get_run_issues():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason=dict(reason='manual'))
        db.session.commit()

        execution.get_run_issues(run.id, token_info=token_info)


@pytest.mark.db
def test_get_run_artifacts():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason=dict(reason='manual'))
        db.session.commit()

        execution.get_run_artifacts(run.id, token_info=token_info)


@pytest.mark.db
def test_get_job_logs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system)
        db.session.commit()

        with patch('clickhouse_driver.Client') as ch:
            execution.get_job_logs(job.id, token_info=token_info)


@pytest.mark.db
def test_cancel_run():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        db.session.commit()

        execution.cancel_run(run.id, token_info=token_info)


@pytest.mark.db
def test_delete_job():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system)
        db.session.commit()

        execution.delete_job(job.id, token_info=token_info)


@pytest.mark.db
def test_get_agent_jobs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agent = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        execution.get_agent_jobs(agent.id, token_info=token_info)
