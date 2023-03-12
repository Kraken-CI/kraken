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

import json
import pytest

from kraken.server import initdb, consts
from kraken.server.models import db, Run, Stage, Flow, Branch, Project, Tool, System, AgentsGroup, Job
from kraken.server.models import Step

from common import create_app, check_missing_tests_in_mod

from kraken.server import datastore


def test_missing_tests():
    check_missing_tests_in_mod(datastore, __name__)


@pytest.mark.db
def test_handle_data():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI)
        run = Run(stage=stage, flow=flow, reason='by me')
        system = System()
        agents_group = AgentsGroup()
        job = Job(run=run, agents_group=agents_group, system=system)
        tool = Tool(fields={})

        step = Step(index=0,
                    job=job,
                    tool=tool,
                    fields={
                        "file": "",
                        "cwd": "",
                        "value": "",
                        "operation": "set",
                        "json_pointer": "",
                        "scope": "",
                    })

        db.session.commit()

        # set data at root
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        step.fields['operation'] = 'set'
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.user_data == data

        # set data at /b
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/b'
        datastore.handle_data(job, step, json.dumps(7))
        assert flow.user_data['a'] == 1
        assert flow.user_data['b'] == 7

        # set data at /a
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/a'
        datastore.handle_data(job, step, json.dumps({'f': 8}))
        assert flow.user_data['a'] == {'f': 8}

        # reset data
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/'
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.user_data == data

        # # get root
        # step.fields['operation'] = 'get'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == data

        # # get /a
        # step.fields['json_pointer'] = '/a'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 1

        # # get /c/1
        # step.fields['json_pointer'] = '/c/1'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 4

        # # get /d/e
        # step.fields['json_pointer'] = '/d/e'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 6

        # set data at root in ci branch
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/'
        step.fields['scope'] = 'branch-ci'
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.branch.user_data_ci == data

        # set data at /d in ci branch
        step.fields['json_pointer'] = '/d'
        step.fields['scope'] = 'branch-ci'
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        datastore.handle_data(job, step, json.dumps(7))
        assert flow.branch.user_data_ci['a'] == 1
        assert flow.branch.user_data_ci['d'] == 7

        # # get /d in ci branch
        # step.fields['operation'] = 'get'
        # step.fields['json_pointer'] = '/d'
        # step.fields['scope'] = 'branch-ci'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 7

        # set data at root in dev branch
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/'
        step.fields['scope'] = 'branch-dev'
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.branch.user_data_dev == data

        # set data at /d in dev branch
        step.fields['json_pointer'] = '/d'
        step.fields['scope'] = 'branch-dev'
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        datastore.handle_data(job, step, json.dumps(8))
        assert flow.branch.user_data_dev['a'] == 1
        assert flow.branch.user_data_dev['d'] == 8

        # # get /d in dev branch
        # step.fields['operation'] = 'get'
        # step.fields['json_pointer'] = '/d'
        # step.fields['scope'] = 'branch-dev'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 8

        # set data at root in branch
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/'
        step.fields['scope'] = 'branch'
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.branch.user_data == data

        # set data at /d in branch
        step.fields['json_pointer'] = '/d'
        step.fields['scope'] = 'branch'
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        datastore.handle_data(job, step, json.dumps(8))
        assert flow.branch.user_data['a'] == 1
        assert flow.branch.user_data['d'] == 8

        # # get /d in branch
        # step.fields['operation'] = 'get'
        # step.fields['json_pointer'] = '/d'
        # step.fields['scope'] = 'branch'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 8

        # set data at root in project
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        step.fields['operation'] = 'set'
        step.fields['json_pointer'] = '/'
        step.fields['scope'] = 'project'
        datastore.handle_data(job, step, json.dumps(data))
        assert flow.branch.project.user_data == data

        # set data at /d in project
        step.fields['json_pointer'] = '/d'
        step.fields['scope'] = 'project'
        data = {'a': 1, 'b': 2, 'c': [3, 4, 5], 'd': {'e': 6}}
        datastore.handle_data(job, step, json.dumps(8))
        assert flow.branch.project.user_data['a'] == 1
        assert flow.branch.project.user_data['d'] == 8

        # # get /d in project
        # step.fields['operation'] = 'get'
        # step.fields['json_pointer'] = '/d'
        # step.fields['scope'] = 'project'
        # resp_data = datastore.handle_data(job, step, None)
        # assert resp_data == 8
