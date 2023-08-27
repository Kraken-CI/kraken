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

import pytest
from hamcrest import assert_that, has_entries, contains

import jinja2

from kraken.server import consts, initdb
from kraken.server.models import db, Project, Branch, Flow, Secret, Stage, AgentsGroup, Agent, Tool
from kraken.server.models import Run, Step, System, Job

from common import create_app

from kraken.server import schema


@pytest.mark.db
def test_substitute_vars():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1', user_data={'aaa': 321})
        branch = Branch(name='br', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123})
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.')
        db.session.commit()

        # simple case str->str
        fields = {'f1': 'aaa #{VAR1} ccc'}
        args = {'VAR1': 'bbb'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == new_fields_masked
        assert new_fields == {'f1': 'aaa bbb ccc'}

        # simple case str->str with secret
        fields = {'f1': 'aaa #{VAR1} ccc #{KK_SECRET_abc}'}
        args = {'VAR1': 'bbb', 'KK_SECRET_abc': 'abc'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == {'f1': 'aaa bbb ccc abc'}
        assert new_fields_masked == {'f1': 'aaa bbb ccc ******'}

        # str->dict->str
        fields = {'f1': {'f2': 'aaa #{Var_1} ccc'}}
        args = {'Var_1': 'bbb'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == new_fields_masked
        assert new_fields == {'f1': {'f2': 'aaa bbb ccc'}}

        # str->dict->str with secret
        fields = {'f1': {'f2': 'aaa #{Var_1} ccc #{KK_SECRET_aBc_2}'}}
        args = {'Var_1': 'bbb', 'KK_SECRET_aBc_2': 'cba'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == {'f1': {'f2': 'aaa bbb ccc cba'}}
        assert new_fields_masked == {'f1': {'f2': 'aaa bbb ccc ******'}}

        # str->array[str]
        fields = {'f1': ['aaa #{Var_1} ccc', '#{vAr_2}']}
        args = {'Var_1': 'bbb', 'vAr_2': 'ddd'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == new_fields_masked
        assert new_fields == {'f1': ['aaa bbb ccc', 'ddd']}

        # str->array[str] with secret
        fields = {'f1': ['aaa #{Var_1} ccc', '#{vAr_2}', 'ee #{KK_SECRET_aBc_2} ff']}
        args = {'Var_1': 'bbb', 'vAr_2': 'ddd', 'KK_SECRET_aBc_2': 'cba'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == {'f1': ['aaa bbb ccc', 'ddd', 'ee cba ff']}
        assert new_fields_masked == {'f1': ['aaa bbb ccc', 'ddd', 'ee ****** ff']}

        # str->array[str, dict->str]
        fields = {'f1': ['aaa #{Var_1} ccc', {'f2': '#{vAr_2}'}]}
        args = {'Var_1': 'bbb', 'vAr_2': 'ddd'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == new_fields_masked
        assert new_fields == {'f1': ['aaa bbb ccc', {'f2': 'ddd'}]}

        # str->array[str, dict->str] with secret
        fields = {'f1': ['aaa #{KK_SECRET_Var_1} ccc', {'f2': '#{KK_SECRET_vAr_2}'}]}
        args = {'KK_SECRET_Var_1': 'bbb', 'KK_SECRET_vAr_2': 'ddd'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == {'f1': ['aaa bbb ccc', {'f2': 'ddd'}]}
        assert new_fields_masked == {'f1': ['aaa ****** ccc', {'f2': '******'}]}

        # complex
        fields = {
            "tool": "artifacts #{KK_SECRET_Var}",
            "source": [
                "kraken-#{KK_SECRET_Var}-compose-0.#{KK_FLOW_SEQ}.yaml",
                ".env",
                "server/dist/krakenci_server-0.#{KK_FLOW_SEQ}.tar.gz",
                "agent/krakenci_agent-0.#{KK_FLOW_SEQ}.tar.gz",
                "client/dist/krakenci_client-0.#{KK_FLOW_SEQ}.tar.gz",
                "ui/dist/krakenci_ui-0.#{KK_FLOW_SEQ}.tar.gz",
            ],
            "cwd": "kraken #{KK_SECRET_Var}",
            "public": True,
            "parameters": [{
                "name": "AMI",
                "type": "string #{KK_SECRET_Var}",
                "default": "ami-0967f290f3533e5a8",
                "description": "AMI for Building"
            }]
        }
        args = {'KK_FLOW_SEQ': '123', 'KK_SECRET_Var': 'abc'}
        ctx = schema.prepare_context(run, args)
        new_fields, new_fields_masked = schema.substitute_vars(fields, args, ctx)
        assert new_fields == {
            'cwd': 'kraken abc',
            'parameters': [{'default': 'ami-0967f290f3533e5a8',
                            'description': 'AMI for Building',
                            'name': 'AMI',
                            'type': 'string abc'}],
            'public': True,
            'source': ['kraken-abc-compose-0.123.yaml',
                       '.env',
                       'server/dist/krakenci_server-0.123.tar.gz',
                       'agent/krakenci_agent-0.123.tar.gz',
                       'client/dist/krakenci_client-0.123.tar.gz',
                       'ui/dist/krakenci_ui-0.123.tar.gz'],
            'tool': 'artifacts abc'}
        assert new_fields_masked == {
            'cwd': 'kraken ******',
            'parameters': [{'default': 'ami-0967f290f3533e5a8',
                            'description': 'AMI for Building',
                            'name': 'AMI',
                            'type': 'string ******'}],
            'public': True,
            'source': ['kraken-******-compose-0.123.yaml',
                       '.env',
                       'server/dist/krakenci_server-0.123.tar.gz',
                       'agent/krakenci_agent-0.123.tar.gz',
                       'client/dist/krakenci_client-0.123.tar.gz',
                       'ui/dist/krakenci_ui-0.123.tar.gz'],
            'tool': 'artifacts ******'}


@pytest.mark.db
def test_substitute_val():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1', user_data={'aaa': 321})
        branch = Branch(name='br', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123})
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system, name='hello')
        tool = Tool(fields={})
        step = Step(index=0,
                    job=job,
                    tool=tool,
                    fields={},
                    fields_raw={})
        db.session.commit()

        args = {'VAR1': 'bbb', 'color': 'red'}
        ctx = schema.prepare_context(step, args)

        val =  'aaa #{flow.data.aaa} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 123 ccc'

        val =  'aaa #{project.data.aaa} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 321 ccc'

        val =  'aaa #{branch.data.aaa} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 234 ccc'

        val =  'aaa #{branch.data_ci.aaa} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == "aaa {'bbb': 234} ccc"

        val =  'aaa #{branch.data_dev.aaa} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 456 ccc'

        val =  'aaa #{branch.name} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa br ccc'

        val =  'aaa #{run.label} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 333. ccc'

        val =  'aaa #{job.name} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa hello ccc'

        val =  'aaa #{step.index} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 0 ccc'

        val =  'aaa #{args.color} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa red ccc'

        ctx = schema.prepare_context(run, args)

        val =  'aaa #{missing} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa <ERROR> ccc'

        ctx = schema.prepare_context(run, args)
        val =  'aaa #{run.label} ccc'
        new_val, new_val_masked = schema.substitute_val(val, args, ctx)
        assert new_val == 'aaa 333. ccc'


@pytest.mark.db
def test_prepare_context():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1', user_data={'aaa': 321})
        branch = Branch(name='br', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123})
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system, name='hello')
        tool = Tool(fields={})
        step = Step(index=0,
                    job=job,
                    tool=tool,
                    fields={},
                    fields_raw={})
        db.session.commit()

        args = {'a': 'b'}

        built_ins = {
            'args': args,
            'project': has_entries({
                'id': proj.id,
                'name': 'proj-1',
                'data': {
                    'aaa': 321,
                },
            }),
            'branch': has_entries({
                'id': branch.id,
                'name': 'br',
                'project_id': proj.id,
                'project_name': 'proj-1',
                'branch_name': None,
                'data': {
                    'aaa': 234
                },
                'data_ci': {
                    'aaa': {'bbb': 234}
                },
                'data_dev': {
                    'aaa': 456
                }
            }),
            'branch_name': 'br',
            'env': {},
            'secrets': {},
            'stage': has_entries({
                'id': stage.id,
                'name': None,
                'description': None,
                'enabled': True,
                'schema_from_repo_enabled': False,
                'repo_url': None,
                'repo_branch': None,
                'repo_access_token': None,
                'repo_state': 0,
                'repo_error': None,
                'repo_refresh_interval': None,
                'git_clone_params': None,
                'repo_version': None,
                'schema_file': None
            }),
            'flow': has_entries({
                'id': flow.id,
                'label': '%d.' % flow.id,
                'state': 'in-progress',
                'kind': 'ci',
                'duration': '0s',
                'branch_name': None,
                'args': {},
                'trigger': None,
                'data': {'aaa': 123}
            }),
            'run': has_entries({
                'id': run.id,
                'label': '333.',
                'started': None,
                'finished': None,
                'processed_at': None,
                'duration': '',
                'state': 'in-progress',
                'stage_name': None,
                'stage_id': stage.id,
                'flow_id': flow.id,
                'flow_kind': 'ci',
                'flow_label': '%d.' % flow.id,
                'args': {},
                'jobs_total': 0,
                'jobs_waiting': 0,
                'jobs_executing': 0,
                'jobs_processing': 0,
                'jobs_error': 0,
                'tests_total': 0,
                'tests_passed': 0,
                'tests_not_run': 0,
                'issues_total': 0,
                'issues_new': 0,
                'new_cnt': 0,
                'no_change_cnt': 0,
                'regr_cnt': 0,
                'fix_cnt': 0,
                'reason': 'by me'
            }),
            'is_ci': True,
            'is_dev': False,
            'run_label': '333.',
            'flow_label': '%d.' % flow.id,
            'job': has_entries({
                'id': job.id,
                'started': None,
                'finished': None,
                'completed': None,
                'duration': '',
                'name': 'hello',
                'state': 2,
                'completion_status': None,
                'timeout': None,
                'covered': False,
                'notes': None,
                'system_id': system.id,
                'system': None,
                'executor': None,
                'run_id': run.id,
                'agents_group_id': agents_group.id,
                'agents_group_name': None,
                'agent_id': 0,
                'agent_name': '',
                'steps': contains(has_entries({
                    'id': step.id,
                    'index': 0,
                    'tool': None,
                    'tool_id': tool.id,
                    'tool_location': None,
                    'tool_entry': None,
                    'tool_version': None,
                    'job_id': job.id,
                    'status': None,
                    'result': None,
                }))
            }),
            'step': has_entries({
                'id': step.id,
                'index': 0,
                'tool': None,
                'tool_id': tool.id,
                'tool_location': None,
                'tool_entry': None,
                'tool_version': None,
                'job_id': job.id,
                'status': None,
                'result': None,
            }),
            'prev_ok': True,
            'always': True,
            'never': False,
            'was_any_error': False,
            'was_no_error': True,
        }

        ctx = schema.prepare_context(step, args)
        assert_that(ctx, has_entries(built_ins))

        built_ins['job'] = None
        built_ins['step'] = None
        ctx = schema.prepare_context(run, args)
        assert_that(ctx, has_entries(built_ins))

        built_ins['run'] = None
        built_ins['flow'] = None
        built_ins['run_label'] = None
        built_ins['flow_label'] = None
        ctx = schema.prepare_context(stage, args)
        assert_that(ctx, has_entries(built_ins))

        built_ins['stage'] = None
        ctx = schema.prepare_context(branch, args)
        assert_that(ctx, has_entries(built_ins))
