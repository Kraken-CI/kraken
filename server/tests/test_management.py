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

import datetime
from unittest.mock import patch

import pytest
from hamcrest import assert_that, has_entries, matches_regexp, contains_exactly, instance_of

import werkzeug.exceptions

from kraken.server import consts, initdb, utils, access
from kraken.server.models import db, Project, Branch, Flow, Secret, Stage, AgentsGroup, Agent, Tool

from common import create_app, prepare_user, check_missing_tests_in_mod

from kraken.server import management


def test_missing_tests():
    check_missing_tests_in_mod(management, __name__)


def test_get_server_version():
    resp, code = management.get_server_version()
    assert code == 200
    assert 'version' in resp
    assert resp['version'] == '0.0'


@pytest.mark.db
def test_create_project():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        body = dict(name='abc')
        management.create_project(body, token_info=token_info)


@pytest.mark.db
def test_update_project():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        db.session.commit()

        body = dict(webhooks='abc')
        management.update_project(proj.id, body, token_info=token_info)


@pytest.mark.db
def test_get_project():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        db.session.commit()

        management.get_project(proj.id, False, token_info=token_info)


@pytest.mark.db
def test_delete_project():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        db.session.commit()

        management.delete_project(proj.id, token_info=token_info)


@pytest.mark.db
def test_get_projects():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        Project(name='proj-1')
        db.session.commit()

        management.get_projects(token_info=token_info)


@pytest.mark.db
def test_create_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        db.session.commit()

        body = dict(name='abc')
        management.create_branch(proj.id, body, token_info=token_info)


@pytest.mark.db
def test_update_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        db.session.commit()

        body = dict(name='abc')
        management.update_branch(branch.id, body, token_info=token_info)


@pytest.mark.db
def test_get_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        db.session.commit()

        management.get_branch(branch.id, token_info=token_info)


@pytest.mark.db
def test_delete_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        db.session.commit()

        management.delete_branch(branch.id, token_info=token_info)


@pytest.mark.db
def test_get_branch_sequences():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        db.session.commit()

        management.get_branch_sequences(branch.id, token_info=token_info)


@pytest.mark.db
def test_move_branch():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj1 = Project(name='proj-1')
        proj2 = Project(name='proj-2')
        br = Branch(name='br', project=proj1)
        db.session.commit()

        with pytest.raises(werkzeug.exceptions.NotFound):
            management.move_branch(123, {}, token_info=token_info)

        with pytest.raises(werkzeug.exceptions.BadRequest):
            management.move_branch(br.id, {}, token_info=token_info)

        assert br.project_id == proj1.id

        # move branch to new project
        management.move_branch(br.id, {'project_id': proj2.id}, token_info=token_info)
        assert br.project_id == proj2.id

        # move branch brack to previous project
        management.move_branch(br.id, {'project_id': proj1.id}, token_info=token_info)
        assert br.project_id == proj1.id


@pytest.mark.db
def test_get_branch_stats():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        br = Branch(name='br', project=proj)
        fc1 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=1)
        fc2 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=2)
        fc3 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=3)
        fc4 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=4)
        fc5 = Flow(branch=br, kind=consts.FLOW_KIND_CI, state=1)
        fd1 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd2 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd3 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        fd4 = Flow(branch=br, kind=consts.FLOW_KIND_DEV)
        db.session.commit()

        today = utils.utcnow()
        two_weeks_ago = today - datetime.timedelta(days=14)
        two_months_ago = today - datetime.timedelta(days=60)
        fc1.created = two_months_ago
        fc1.finished = fc1.created + datetime.timedelta(seconds=60)
        fc2.created = two_months_ago + datetime.timedelta(seconds=10)
        fc3.created = two_weeks_ago
        fc3.finished = fc3.created + datetime.timedelta(seconds=180)
        fc4.created = two_weeks_ago + datetime.timedelta(seconds=10)
        fc4.finished = fc4.created + datetime.timedelta(seconds=120)
        fd1.created = two_months_ago
        fd1.finished = fd1.created + datetime.timedelta(seconds=30)
        fd2.created = two_months_ago + datetime.timedelta(seconds=10)
        fd2.finished = fd2.created + datetime.timedelta(seconds=60)
        fd3.created = two_weeks_ago
        fd3.finished = fd3.created + datetime.timedelta(seconds=30)
        fd4.finished = fd4.created + datetime.timedelta(seconds=90)
        db.session.commit()

        with pytest.raises(werkzeug.exceptions.NotFound):
            management.get_branch_stats(123, token_info=token_info)

        resp, code = management.get_branch_stats(br.id, token_info=token_info)
        assert code == 200
        # assert resp is None
        lbl_re = matches_regexp(r'\d+\.')
        assert_that(resp, has_entries({
            'id': br.id,
            'ci': has_entries({
                'flows_total': 5,
                'flows_last_month': 3,
                'flows_last_week': 1,
                'avg_duration_last_month': '2m 30s',
                'avg_duration_last_week': None,
                'durations': instance_of(list),
            }),
            'dev': has_entries({
                'flows_total': 4,
                'flows_last_month': 2,
                'flows_last_week': 1,
                'avg_duration_last_month': '0s',
                'avg_duration_last_week': '1m 30s',
                'durations': instance_of(list),
            }),
        }))

        assert_that(resp['ci']['durations'],
                    contains_exactly(has_entries({'flow_label': lbl_re, 'duration': 60}),
                                     has_entries({'flow_label': lbl_re, 'duration': None}),
                                     has_entries({'flow_label': lbl_re, 'duration': 180}),
                                     has_entries({'flow_label': lbl_re, 'duration': 120}),
                                     has_entries({'flow_label': lbl_re, 'duration': None})))

        assert_that(resp['dev']['durations'],
                    contains_exactly(has_entries({'flow_label': lbl_re, 'duration': 30}),
                                     has_entries({'flow_label': lbl_re, 'duration': 60}),
                                     has_entries({'flow_label': lbl_re, 'duration': 30}),
                                     has_entries({'flow_label': lbl_re, 'duration': 90})))


def test_get_workflow_schema():
    app = create_app()

    with app.app_context():
        schema, code = management.get_workflow_schema()
        assert schema
        assert code == 200


@pytest.mark.db
def test_create_secret():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        db.session.commit()

        body = dict(kind='simple', secret='abc', name='def')
        management.create_secret(proj.id, body, token_info=token_info)


@pytest.mark.db
def test_update_secret():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        secret = Secret(name="abc", project=proj, data={})
        db.session.commit()

        body = dict(secret='abc', kind=consts.SECRET_KIND_SIMPLE)
        management.update_secret(secret.id, body, token_info=token_info)


@pytest.mark.db
def test_delete_secret():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        secret = Secret(name="abc", project=proj, data={})
        db.session.commit()

        management.delete_secret(secret.id, token_info=token_info)


@pytest.mark.db
def test_create_stage():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        initdb._prepare_builtin_tools()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        db.session.commit()

        body = dict(name='abc')
        management.create_stage(branch.id, body, token_info=token_info)


@pytest.mark.db
def test_get_stage():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        stage = Stage(branch=branch, schema={})
        db.session.commit()

        management.get_stage(stage.id, token_info=token_info)


@pytest.mark.db
def test_update_stage():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        stage = Stage(branch=branch, schema={})
        db.session.commit()

        body = dict(name='abc')
        management.update_stage(stage.id, body, token_info=token_info)


@pytest.mark.db
def test_delete_stage():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        stage = Stage(branch=branch, schema={})
        db.session.commit()

        management.delete_stage(stage.id, token_info=token_info)


@pytest.mark.db
def test_get_stage_schema_as_json():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        stage = Stage(branch=branch, schema={})
        db.session.commit()

        body = {}
        management.get_stage_schema_as_json(stage.id, body, token_info=token_info)


@pytest.mark.db
def test_get_stage_schedule():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        proj = Project(name='proj-1')
        branch = Branch(name='br', project=proj)
        stage = Stage(branch=branch, schema={})
        db.session.commit()

        management.get_stage_schedule(stage.id, token_info=token_info)


@pytest.mark.db
def test_get_agent():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agent = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        management.get_agent(agent.id, token_info=token_info)


@pytest.mark.db
def test_get_agents():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        management.get_agents(token_info=token_info)


@pytest.mark.db
def test_update_agents():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agent = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        body = dict()
        management.update_agents(body, token_info=token_info)


@pytest.mark.db
def test_update_agent():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agent = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        body = dict()
        management.update_agent(agent.id, body, token_info=token_info)


@pytest.mark.db
def test_delete_agent():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agent = Agent(name='agent', address='1.2.3.4', authorized=True, disabled=False)
        db.session.commit()

        management.delete_agent(agent.id, token_info=token_info)


@pytest.mark.db
def test_get_group():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agents_group = AgentsGroup()
        db.session.commit()

        management.get_group(agents_group.id, token_info=token_info)


@pytest.mark.db
def test_get_groups():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        AgentsGroup()
        db.session.commit()

        management.get_groups(token_info=token_info)


@pytest.mark.db
def test_create_group():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        body = dict(name='abc')
        management.create_group(body, token_info=token_info)


@pytest.mark.db
def test_update_group():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agents_group = AgentsGroup()
        db.session.commit()

        body = dict(name='abc')
        management.update_group(agents_group.id, body, token_info=token_info)


@pytest.mark.db
def test_delete_group():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        agents_group = AgentsGroup()
        db.session.commit()

        management.delete_group(agents_group.id, token_info=token_info)


@pytest.mark.db
def test_get_aws_ec2_regions():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with pytest.raises(werkzeug.exceptions.InternalServerError) as ex:
            management.get_aws_ec2_regions(token_info=token_info)
        assert "Incorrect AWS credential" in str(ex.value)


@pytest.mark.db
def test_get_aws_ec2_instance_types():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with pytest.raises(werkzeug.exceptions.InternalServerError) as ex:
            management.get_aws_ec2_instance_types('region', token_info=token_info)
        assert "Incorrect AWS credential" in str(ex.value)


@pytest.mark.db
def test_get_azure_locations():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with pytest.raises(werkzeug.exceptions.InternalServerError) as ex:
            management.get_azure_locations(token_info=token_info)
        assert "Incorrect Azure credential" in str(ex.value)


@pytest.mark.db
def test_get_azure_vm_sizes():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with pytest.raises(werkzeug.exceptions.InternalServerError) as ex:
            management.get_azure_vm_sizes('location', token_info=token_info)
        assert "Incorrect Azure credential" in str(ex.value)


@pytest.mark.db
def test_get_settings():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        management.get_settings(token_info=token_info)


@pytest.mark.db
def test_update_settings():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        body = {}
        management.update_settings(body, token_info=token_info)


@pytest.mark.db
def test_get_diagnostics():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with pytest.raises(KeyError) as ex:
            management.get_diagnostics(token_info=token_info)
        assert "MINIO_ACCESS_KEY" in str(ex.value)


@pytest.mark.db
def test_get_last_rq_jobs_names():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with patch('clickhouse_driver.Client'):
            management.get_last_rq_jobs_names(token_info=token_info)


@pytest.mark.db
def test_get_services_logs():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        with patch('clickhouse_driver.Client'):
            management.get_services_logs([], token_info=token_info)


@pytest.mark.db
def test_get_errors_in_logs_count():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        management.get_errors_in_logs_count()


@pytest.mark.db
def test_get_settings_working_state():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        management.get_settings_working_state('email', token_info=token_info)


@pytest.mark.db
def test_get_systems():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        management.get_systems()


@pytest.mark.db
def test_get_tools():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        management.get_tools()


@pytest.mark.db
def test_get_tool_versions():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        management.get_tool_versions('shell')


@pytest.mark.db
def test_create_or_update_tool():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        body = {
            "name": "abc",
            "description": "Abc.",
            "location": ".",
            "entry": "main",
            "parameters": {
                "additionalProperties": False,
                "required": ["pkgs"],
                "properties": {
                    "pkgs": {
                        "description": "Abc.",
                        "type": "string"
                    },
                    "provider": {
                        "description": "Abc",
                        "enum": ["a", "b"]
                    }
                }
            }
        }

        management.create_or_update_tool(body, token_info=token_info)


@pytest.mark.db
def atest_upload_new_or_overwrite_tool():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        body = dict(meta={
            "name": "abc",
            "description": "Abc.",
            "location": ".",
            "entry": "main",
            "parameters": {
                "additionalProperties": False,
                "required": ["pkgs"],
                "properties": {
                    "pkgs": {
                        "description": "Abc.",
                        "type": "string"
                    },
                    "provider": {
                        "description": "Abc",
                        "enum": ["a", "b"]
                    }
                }
            }
        })

        management.upload_new_or_overwrite_tool('abc', body, None, token_info=token_info)


@pytest.mark.db
def test_delete_tool():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        tool = Tool(name='t', fields={}, location='l', entry='e')
        db.session.commit()

        management.delete_tool(tool.id, token_info=token_info)
