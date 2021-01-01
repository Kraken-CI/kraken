import sys
import logging
from unittest.mock import patch

import pytest

import sqlalchemy
from flask import Flask

from kraken.server import consts
from kraken.server.models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, Issue, System, AgentsGroup, TestCase, Tool

from kraken.server.bg import jobs
#import kraken.agent.config

log = logging.getLogger(__name__)


def create_empty_db(db_name, drop_exisiting=False):
    db_root_url = 'postgresql://kk:kk@localhost:5678/'

    # check if db exists
    engine = sqlalchemy.create_engine(db_root_url + db_name, echo=False)
    db_exists = False
    try:
        connection = engine.connect()
        connection.execute('select 1')
        connection.close()
        db_exists = True
    except:
        pass

    engine = sqlalchemy.create_engine(db_root_url, echo=False)
    connection = engine.connect()

    if db_exists and drop_exisiting:
        connection.execute("commit;")
        connection.execute("DROP DATABASE %s;" % db_name)
        db_exists = False

    # create db if missing
    if not db_exists:
        connection.execute("commit;")
        connection.execute("CREATE DATABASE %s;" % db_name)

    connection.close()

    return db_root_url, db_exists

def clear_db_postresql(engine):
    for table in db.metadata.tables.keys():
        engine.execute('ALTER TABLE "%s" DISABLE TRIGGER ALL;' % table)
        try:
            engine.execute('DELETE FROM "%s";' % table)
        except Exception as e:
            if not "doesn't exist" in str(e):
                raise
        engine.execute('ALTER TABLE "%s" ENABLE TRIGGER ALL;' % table)


def prepare_db():
    # session.close_all()
    # if metadata.bind:
    #     metadata.bind.dispose()

    db_name = 'kkdb'

    db_root_url, db_exists = create_empty_db(db_name)

    # prepare connection, create any missing tables
    #clean_db()
    real_db_url = db_root_url + db_name
    # engine = sqlalchemy.create_engine(real_db_url, echo=False)
    # db.metadata.bind = engine
    # db.setup_all()
    # db.create_all()
    # db.fix_compatibility()

    # if db_exists:
    #     global_log.log_global('prepare_db - delete all rows', 'real_db_url', real_db_url)
    #     # delete all rows from all tables
    #     if db_url.startswith("mysql"):
    #         clear_db_mysql(engine)
    #     elif db_url.startswith("postgresql"):
    #         clear_db_postresql(engine)

    # db.prepare_indexes(engine)
    return real_db_url


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
            run = Run(stage=stage, flow=flow)
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
            run = Run(stage=stage, flow=flow)
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
        run = Run(stage=stage, flow=flow)
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
        tool = Tool(fields={})
        test_case = TestCase(tool=tool)
        db.session.commit()

        def new_issue(line, issue_type, completion_status=consts.JOB_CMPLT_ALL_OK):
            flow = Flow(branch=branch)
            run = Run(stage=stage, flow=flow)
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
