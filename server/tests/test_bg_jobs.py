# Copyright 2020-2021 The Kraken Authors
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
import logging

import pytest

import sqlalchemy
from flask import Flask

from kraken.server import consts
from kraken.server.models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, Issue, System, AgentsGroup, TestCase, Tool
from kraken.server.bg import jobs

from dbtest import prepare_db

log = logging.getLogger(__name__)


def _create_app():
    # addresses
    db_url = prepare_db()

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)
    db.create_all(app=app)

    return app


@pytest.mark.db
def test__analyze_job_results_history__1_job_basic():
    app = _create_app()

    with app.app_context():
        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        test_case = TestCase(tool=tool)
        db.session.commit()

        def new_result(result):
            flow = Flow(branch=branch)
            run = Run(stage=stage, flow=flow, reason='by me')
            job = Job(run=run, agents_group=agents_group, system=system)
            tcr = TestCaseResult(test_case=test_case, result=result)
            job.results = [tcr]
            db.session.commit()
            return job, tcr

        # result 0 - PASSED
        log.info('result 0 - PASSED')
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 1
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_NEW

        # result 1 - PASSED
        log.info('result 1 - PASSED')
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO

        # result 2 - FAILED
        job, tcr = new_result(consts.TC_RESULT_FAILED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 1
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 3 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 1
        assert tcr.instability == 2
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_FIX

        # result 4 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 2
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO


@pytest.mark.db
def test__analyze_job_results_history__1_job_with_cover():
    app = _create_app()

    with app.app_context():
        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        test_case = TestCase(tool=tool)
        db.session.commit()

        def new_result(result):
            flow = Flow(branch=branch)
            run = Run(stage=stage, flow=flow, reason='by me')
            job = Job(run=run, agents_group=agents_group, system=system)
            tcr = TestCaseResult(test_case=test_case, result=result)
            job.results = [tcr]
            db.session.commit()
            return job, tcr

        # result 0 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 1
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_NEW

        # result 1 - FAILED
        flow = Flow(branch=branch)
        run = Run(stage=stage, flow=flow, reason='by me')
        job1 = Job(run=run, agents_group=agents_group, system=system)
        tcr = TestCaseResult(test_case=test_case, result=consts.TC_RESULT_FAILED)
        job1.results = [tcr]
        db.session.commit()
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job1)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 1
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 1 covered - PASSED
        job1.covered = True
        job2 = Job(run=run, agents_group=agents_group, system=system)
        tcr = TestCaseResult(test_case=test_case, result=consts.TC_RESULT_PASSED)
        job2.results = [tcr]
        db.session.commit()
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job2)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO

        # result 2 - FAILED
        job, tcr = new_result(consts.TC_RESULT_FAILED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 1
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 3 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        new_cnt, no_change_cnt, regr_cnt, fix_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 1
        assert tcr.instability == 2
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_FIX


@pytest.mark.db
def test__analyze_job_issues_history():
    app = _create_app()

    with app.app_context():
        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        agents_group = AgentsGroup()
        db.session.commit()

        def new_issue(line, issue_type, completion_status=consts.JOB_CMPLT_ALL_OK):
            flow = Flow(branch=branch)
            run = Run(stage=stage, flow=flow, reason='by me')
            job = Job(run=run, agents_group=agents_group, system=system, completion_status=completion_status)
            issue = Issue(line=line, issue_type=issue_type)
            job.issues = [issue]
            db.session.commit()
            return job, issue

        # issue 0
        job, issue = new_issue(10, consts.ISSUE_TYPE_ERROR)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 0
        assert issue.age == 0

        # issue 2
        job, issue = new_issue(10, consts.ISSUE_TYPE_ERROR)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 0
        assert issue.age == 1

        # issue 3, several lines moved but still the same
        job, issue = new_issue(12, consts.ISSUE_TYPE_ERROR)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 0
        assert issue.age == 2

        # issue 4, same line but different type so new issue
        job, issue = new_issue(12, consts.ISSUE_TYPE_WARNING)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 1
        assert issue.age == 0

        # issue 5, the same
        job, issue = new_issue(12, consts.ISSUE_TYPE_WARNING)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 0
        assert issue.age == 1

        # issue 6, but job with error so it should be skipped
        job, issue = new_issue(12, consts.ISSUE_TYPE_WARNING, consts.JOB_CMPLT_AGENT_ERROR_RETURNED)

        # issue 7, it should take 5 as prev so age = 2
        job, issue = new_issue(12, consts.ISSUE_TYPE_WARNING)
        new_cnt = jobs._analyze_job_issues_history(job)
        assert new_cnt == 0
        assert issue.age == 2
