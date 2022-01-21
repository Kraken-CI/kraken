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

import pytest

from kraken.server import consts, initdb
from kraken.server.models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, System, AgentsGroup, TestCase, Tool
from kraken.server import execution

from common import create_app

log = logging.getLogger(__name__)


@pytest.mark.db
def test_create_or_update_test_case_comment():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        system2 = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        test_case = TestCase(tool=tool)
        flow = Flow(branch=branch)
        run = Run(stage=stage, flow=flow, reason='by me')
        job = Job(run=run, agents_group=agents_group, system=system, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
        tcr = TestCaseResult(test_case=test_case, result=consts.TC_RESULT_PASSED, job=job)
        job2 = Job(run=run, agents_group=agents_group, system=system2, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
        tcr2 = TestCaseResult(test_case=test_case, result=consts.TC_RESULT_PASSED, job=job2)
        db.session.commit()

        resp, code = execution.create_or_update_test_case_comment(tcr.id,
                                                                  dict(text='text', author='author', state=consts.TC_COMMENT_INVESTIGATING))
        assert code == 200
        assert resp['id'] == 1
        assert resp['state'] == consts.TC_COMMENT_INVESTIGATING
        assert len(resp['data']) == 1
        assert resp['data'][0]['author'] == 'author'
        assert resp['data'][0]['date'].startswith('20')
        assert resp['data'][0]['text'] == 'text'
        # checkc if assigning other tcrs with the same tc and flow works
        assert tcr2.comment_id == tcr.comment_id

        resp, code = execution.create_or_update_test_case_comment(tcr.id,
                                                                  dict(text='text2', author='author2', state=consts.TC_COMMENT_BUG_IN_PRODUCT))
        assert code == 200
        assert resp['id'] == 1
        assert resp['state'] == consts.TC_COMMENT_BUG_IN_PRODUCT
        assert len(resp['data']) == 2
        assert resp['data'][0]['author'] == 'author2'
        assert resp['data'][0]['date'].startswith('20')
        assert resp['data'][0]['text'] == 'text2'
        assert resp['data'][1]['author'] == 'author'
        assert resp['data'][1]['date'].startswith('20')
        assert resp['data'][1]['text'] == 'text'
