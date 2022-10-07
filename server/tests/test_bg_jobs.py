# Copyright 2020-2022 The Kraken Authors
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
from unittest.mock import patch

import pytest

from kraken.server import consts, initdb
from kraken.server.models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, Issue, System, AgentsGroup, TestCase, Tool
from kraken.server.bg import jobs

from common import create_app

log = logging.getLogger(__name__)


@pytest.mark.db
def test__analyze_job_results_history__1_job_basic():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

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
            job = Job(run=run, agents_group=agents_group, system=system, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            tcr = TestCaseResult(test_case=test_case, result=result)
            job.results = [tcr]
            db.session.commit()
            return job, tcr

        # result 0 - PASSED
        log.info('result 0 - PASSED')
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
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
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO

        # result 2 - FAILED
        job, tcr = new_result(consts.TC_RESULT_FAILED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 1
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 3 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 1
        assert tcr.instability == 2
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_FIX

        # result 4 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 2
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO


@pytest.mark.db
def test__analyze_job_results_history__1_job_with_cover():
    app = create_app()

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
            job = Job(run=run, agents_group=agents_group, system=system, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            tcr = TestCaseResult(test_case=test_case, result=result)
            job.results = [tcr]
            db.session.commit()
            return job, tcr

        # result 0 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
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
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job1)
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
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job2)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 1
        assert tcr.change == consts.TC_RESULT_CHANGE_NO

        # result 2 - FAILED
        job, tcr = new_result(consts.TC_RESULT_FAILED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 1
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 3 - PASSED
        job, tcr = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 1
        assert tcr.instability == 2
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_FIX


@pytest.mark.db
def test__analyze_job_issues_history():
    app = create_app()

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


@pytest.mark.db
def test__analyze_job_results_history__1_job_flow_dev():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        test_case = TestCase(tool=tool)
        db.session.commit()

        def new_result(result):
            flow = Flow(branch=branch, kind=consts.FLOW_KIND_DEV)
            run = Run(stage=stage, flow=flow, reason='by me')
            job = Job(run=run, agents_group=agents_group, system=system, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            tcr = TestCaseResult(test_case=test_case, result=result)
            job.results = [tcr]
            db.session.commit()
            return job, tcr, flow

        # result 0 - PASSED
        log.info('result 0 - PASSED')
        job, tcr, flow = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 1
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_NEW

        # result 1 - PASSED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        tcr.age = 3
        tcr.instability = 8
        db.session.commit()
        job, tcr, flow = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 8  # should be the same as ref tcr
        assert tcr.age == 3  # should be the same as ref tcr
        assert tcr.change == consts.TC_RESULT_CHANGE_NO

        # result 2 - FAILED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        tcr.age = 0
        tcr.instability = 0
        db.session.commit()
        job, tcr, flow = new_result(consts.TC_RESULT_FAILED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 1
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_REGR

        # result 3 - PASSED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, tcr, flow = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 1
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_FIX

        # result 4 - PASSED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, tcr, flow = new_result(consts.TC_RESULT_PASSED)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 0
        assert tcr.instability == 0
        assert tcr.age == 0
        assert tcr.change == consts.TC_RESULT_CHANGE_NO


@pytest.mark.db
@pytest.mark.parametrize("flow_kind", [consts.FLOW_KIND_CI, consts.FLOW_KIND_DEV])
def test__analyze_job_results_history__2_jobs(flow_kind):
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system = System()
        agents_group = AgentsGroup()
        tool = Tool(fields={})
        test_case1 = TestCase(tool=tool)
        test_case2 = TestCase(tool=tool)
        db.session.commit()

        def new_results(result1, result2, flow_kind):
            flow = Flow(branch=branch, kind=flow_kind)
            run = Run(stage=stage, flow=flow, reason='by me')
            job = Job(run=run, agents_group=agents_group, system=system, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            tcr1 = TestCaseResult(test_case=test_case1, result=result1)
            tcr2 = TestCaseResult(test_case=test_case2, result=result2)
            job.results = [tcr1, tcr2]
            db.session.commit()
            return job, flow

        # results 0: PASSED, PASSED
        job, flow = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED, flow_kind)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 2
        assert no_change_cnt == 0
        assert regr_cnt == 0
        assert fix_cnt == 0

        # results 1 - PASSED->PASSED, PASSED->FAILED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, flow = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_FAILED, flow_kind)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 1
        assert fix_cnt == 0

        # results 2 - PASSED->ERROR, FAILED->ERROR
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, flow = new_results(consts.TC_RESULT_ERROR, consts.TC_RESULT_ERROR, flow_kind)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 1
        assert fix_cnt == 0

        # results 3 - ERROR->PASSED, ERROR->FAILED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, flow = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_FAILED, flow_kind)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 1

        # result 4 - PASSED->PASSED, FAILED->PASSED
        flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        job, flow = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED, flow_kind)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = jobs._analyze_job_results_history(job)
        assert new_cnt == 0
        assert no_change_cnt == 1
        assert regr_cnt == 0
        assert fix_cnt == 1


@pytest.mark.db
@pytest.mark.parametrize("flow_kind", [consts.FLOW_KIND_CI, consts.FLOW_KIND_DEV])
def test_analyze_results_history(flow_kind):
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(77777777)
            mylog.error.assert_called_with('got unknown run to analyze results history: %s', 77777777)

        project = Project()
        branch = Branch(project=project)
        stage = Stage(branch=branch, schema={})
        system1 = System()
        system2 = System()
        agents_group1 = AgentsGroup()
        agents_group2 = AgentsGroup()
        tool = Tool(fields={})
        test_case1 = TestCase(name='tc1', tool=tool)
        test_case2 = TestCase(name='tc2', tool=tool)
        db.session.commit()

        def new_results(result1, result2, result3, result4, result5, result6, flow_kind):
            flow = Flow(branch=branch, kind=flow_kind)
            run = Run(stage=stage, flow=flow, reason='by me')
            job1 = Job(run=run, agents_group=agents_group1, system=system1, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            job2 = Job(run=run, agents_group=agents_group2, system=system2, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            job3 = Job(run=run, agents_group=agents_group2, system=system1, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            job4 = Job(run=run, agents_group=agents_group1, system=system2, completion_status=consts.JOB_CMPLT_ALL_OK, state=consts.JOB_STATE_COMPLETED)
            tcr1 = TestCaseResult(test_case=test_case1, result=result1)
            job1.results = [tcr1]
            tcr2 = TestCaseResult(test_case=test_case2, result=result2)
            job2.results = [tcr2]
            tcr3 = TestCaseResult(test_case=test_case1, result=result3)
            tcr4 = TestCaseResult(test_case=test_case2, result=result4)
            job3.results = [tcr3, tcr4]
            tcr5 = TestCaseResult(test_case=test_case1, result=result5)
            tcr6 = TestCaseResult(test_case=test_case2, result=result6)
            job4.results = [tcr5, tcr6]
            db.session.commit()
            return run, (tcr1, tcr2, tcr3, tcr4, tcr5, tcr6)

        # flow 0: all PASSED
        run, tcrs = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                             consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                             consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                             flow_kind)
        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(run.id)
            assert mylog.info.call_args_list[0][0][0] == 'starting results history analysis of run %s, flow %s [%s] '
            assert mylog.info.call_args_list[0][0][1].id == run.id
            assert mylog.info.call_args_list[0][0][2].id == run.flow.id
            assert mylog.info.call_args_list[0][0][3] == 'CI' if flow_kind == consts.FLOW_KIND_CI else 'DEV'
            if flow_kind == consts.FLOW_KIND_CI:
                assert mylog.info.call_count == 19
                assert mylog.info.call_args_list[1][0][0].startswith('this is the first run')
            else:
                assert mylog.info.call_count == 24
                assert mylog.info.call_args_list[1][0][0] == 'NO REF TCR, ie. new'
                assert mylog.info.call_args_list[21][0][0] == 'run %s: new:%d no-change:%d regr:%d fix:%d'
                assert mylog.info.call_args_list[21][0][2] == 6
                assert mylog.info.call_args_list[21][0][3] == 0
                assert mylog.info.call_args_list[21][0][4] == 0
                assert mylog.info.call_args_list[21][0][5] == 0

        # flow 1 - introduced all other types of results
        run.flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        run.state = consts.RUN_STATE_IN_PROGRESS
        db.session.commit()
        prev_run = run
        run, tcrs = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_FAILED,
                                consts.TC_RESULT_ERROR, consts.TC_RESULT_NOT_RUN,
                                consts.TC_RESULT_DISABLED, consts.TC_RESULT_UNSUPPORTED,
                                flow_kind)
        if flow_kind == consts.FLOW_KIND_CI:
            with patch('kraken.server.bg.jobs.log') as mylog:
                jobs._analyze_results_history(run.id)
                assert mylog.info.call_count == 2
                assert mylog.info.call_args_list[0][0][0] == 'starting results history analysis of run %s, flow %s [%s] '
                assert mylog.info.call_args_list[0][0][1].id == run.id
                assert mylog.info.call_args_list[0][0][2].id == run.flow.id
                assert mylog.info.call_args_list[0][0][3] == 'CI'
                assert mylog.info.call_args_list[1][0][0] == 'postpone anlysis of run %s as prev run %s is not processed yet'
                assert mylog.info.call_args_list[1][0][1].id == run.id
                assert mylog.info.call_args_list[1][0][2].id == prev_run.id

        def _check_logs_ci(mylog, tcrs, run):
            assert mylog.info.call_count == 14
            assert mylog.info.call_args_list[0][0][0] == 'starting results history analysis of run %s, flow %s [%s] '
            assert mylog.info.call_args_list[0][0][1].id == run.id
            assert mylog.info.call_args_list[0][0][2].id == run.flow.id
            assert mylog.info.call_args_list[0][0][3] == 'CI'
            tcr_ids = [tcr.id for tcr in tcrs]
            tc_names = [tcr.test_case.name for tcr in tcrs]
            calls = mylog.info.call_args_list
            for idx in [1, 3, 5, 6, 8, 9]:
                assert calls[idx][0][0] == 'Analyzed result dt:%0.5f %s %s: %s'
                assert calls[idx][0][2].id in tcr_ids
                tcr_ids.remove(calls[idx][0][2].id)
                assert calls[idx][0][3] in tc_names
                tc_names.remove(calls[idx][0][3])
            assert len(tcr_ids) == 0  # all tcr should have been found
            assert len(tc_names) == 0

            assert calls[11][0][0] == 'run %s: new:%d no-change:%d regr:%d fix:%d'
            assert calls[12][0][0] == 'history anlysis of run %s completed'
            assert calls[13][0][0] == 'finished results history analysis of run %s, flow %s [%s]'

        def _check_logs_dev(mylog, tcrs, run):
            assert mylog.info.call_count == 14
            assert mylog.info.call_args_list[0][0][0] == 'starting results history analysis of run %s, flow %s [%s] '
            assert mylog.info.call_args_list[0][0][1].id == run.id
            assert mylog.info.call_args_list[0][0][2].id == run.flow.id
            assert mylog.info.call_args_list[0][0][3] == 'DEV'
            tcr_ids = [tcr.id for tcr in tcrs]
            tc_names = [tcr.test_case.name for tcr in tcrs]
            calls = mylog.info.call_args_list
            for idx in [1, 3, 5, 6, 8, 9]:
                assert calls[idx][0][0] == 'Analyzed result dt:%0.5f %s %s: %s'
                assert calls[idx][0][2].id in tcr_ids
                tcr_ids.remove(calls[idx][0][2].id)
                assert calls[idx][0][3] in tc_names
                tc_names.remove(calls[idx][0][3])
            assert len(tcr_ids) == 0
            assert len(tc_names) == 0

            assert calls[11][0][0] == 'run %s: new:%d no-change:%d regr:%d fix:%d'
            assert calls[12][0][0] == 'history anlysis of run %s completed'
            assert calls[13][0][0] == 'finished results history analysis of run %s, flow %s [%s]'

        def _check_logs(mylog, tcrs, run):
            if flow_kind == consts.FLOW_KIND_CI:
                _check_logs_ci(mylog, tcrs, run)
            else:
                _check_logs_dev(mylog, tcrs, run)

        prev_run.state = consts.RUN_STATE_PROCESSED
        db.session.commit()
        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(run.id)
            _check_logs(mylog, tcrs, run)

        db.session.refresh(run)
        assert run.new_cnt == 0
        assert run.no_change_cnt == 1
        assert run.regr_cnt == 5
        assert run.fix_cnt == 0
        assert run.state == consts.RUN_STATE_PROCESSED

        # flow 2 - shuffled some results
        run.flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        prev_run = run
        run, tcrs = new_results(consts.TC_RESULT_FAILED, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_ERROR, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_UNSUPPORTED, consts.TC_RESULT_DISABLED,
                                flow_kind)
        prev_run.state = consts.RUN_STATE_PROCESSED
        db.session.commit()
        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(run.id)
            _check_logs(mylog, tcrs, run)

        db.session.refresh(run)
        assert run.new_cnt == 0
        assert run.no_change_cnt == 3
        assert run.regr_cnt == 1
        assert run.fix_cnt == 2
        assert run.state == consts.RUN_STATE_PROCESSED

        # flow 3 - no changes
        run.flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        prev_run = run
        run, tcrs = new_results(consts.TC_RESULT_FAILED, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_ERROR, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_UNSUPPORTED, consts.TC_RESULT_DISABLED,
                                flow_kind)
        prev_run.state = consts.RUN_STATE_PROCESSED
        db.session.commit()
        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(run.id)
            _check_logs(mylog, tcrs, run)

        db.session.refresh(run)
        assert run.new_cnt == 0
        assert run.no_change_cnt == 6
        assert run.regr_cnt == 0
        assert run.fix_cnt == 0
        assert run.state == consts.RUN_STATE_PROCESSED

        # flow 3 - back to all PASSED
        run.flow.kind = consts.FLOW_KIND_CI  # move prev flow from dev to ci
        db.session.commit()
        prev_run = run
        run, tcrs = new_results(consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                                consts.TC_RESULT_PASSED, consts.TC_RESULT_PASSED,
                                flow_kind)
        prev_run.state = consts.RUN_STATE_PROCESSED
        db.session.commit()
        with patch('kraken.server.bg.jobs.log') as mylog:
            jobs._analyze_results_history(run.id)
            _check_logs(mylog, tcrs, run)

        db.session.refresh(run)
        assert run.new_cnt == 0
        assert run.no_change_cnt == 2
        assert run.regr_cnt == 0
        assert run.fix_cnt == 4
        assert run.state == consts.RUN_STATE_PROCESSED


@pytest.mark.db
def test_load_remote_tool():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        url = 'https://github.com/Kraken-CI/kraken-tools.git'
        tag = 'main'
        tool_file = 'pkg_install/tool.json'
        tool = Tool(name=url, version=tag, url=url, tag=tag, tool_file=tool_file, fields={})
        db.session.commit()

        os.environ['MINIO_ACCESS_KEY'] = 'UFSEHRCFU4ACUEWHCHWU'
        os.environ['MINIO_SECRET_KEY'] = 'HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY'
        try:
            jobs.load_remote_tool(tool.id)
        finally:
            del os.environ['MINIO_ACCESS_KEY']
            del os.environ['MINIO_SECRET_KEY']
