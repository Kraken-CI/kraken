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
import json
import time
import logging
import xmlrpc.client
from collections import defaultdict

from flask import Flask
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import joinedload
import giturlparse
import pytimeparse
import redis

from ..models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, get_setting
from ..models import AgentsGroup, Agent, System, TestCaseComment, Tool
from ..models import RepoChanges, Secret
from ..schema import prepare_new_planner_triggers
from ..schema import check_and_correct_stage_schema, prepare_context
from ..cloud import cloud
from .. import exec_utils  # pylint: disable=cyclic-import
from .. import consts
from .. import notify
from .. import logs
from .. import gitops
from .. import kkrq
from .. import utils
from .. import dbutils
from .. import toolops
from .. import toolutils


log = logging.getLogger(__name__)


def _create_app(task_name):
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)

    logs.setup_logging('rq')
    log.set_ctx(tool=task_name)

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url + '?application_name=rq_' + task_name
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    # setup sentry
    with app.app_context():
        sentry_url = get_setting('monitoring', 'sentry_dsn')
        logs.setup_sentry(sentry_url)

    return app


def _trigger_stages(run):
    """Trigger the following stages after just completed run_id stage."""
    log.info('starting triggering stages after run %s', run)

    # go through next stages and trigger them if needed
    curr_stage_name = run.stage.name
    branch = run.stage.branch
    for stage in branch.stages:
        if stage.deleted:
            continue
        if stage.schema['parent'] != curr_stage_name:
            # skip stages that are not childs of completed run's stage
            continue
        if not stage.schema['triggers'].get('parent', False) and not stage.schema['triggers'].get('manual', False):
            # skip stages that have parent trigger set to False
            # or that have no manual trigger
            continue

        if stage.enabled:
            exec_utils.start_run(stage, run.flow, reason=dict(reason='parent', run_id=run.id))
        else:
            log.info('stage %s not started because it is disabled', stage)


def _prepare_flow_summary(flow):
    if flow.kind != consts.FLOW_KIND_CI:
        return

    # update pointer to last, completed, CI flow in the branch
    # and if needed then reset pointer to incomplete flow

    # update completed
    last_flow = flow.branch.ci_last_completed_flow
    if last_flow is None or last_flow.created < flow.created:
        flow.branch.ci_last_completed_flow = flow

    # update incomplete
    last_flow = flow.branch.ci_last_incomplete_flow
    if last_flow and last_flow.id == flow.id:
        flow.branch.ci_last_incomplete_flow = None

    db.session.commit()

    # get flow summary and store it in redis to cache it;
    # it will be used e.g. to provide badge info

    # get redis reference
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    redis_host, redis_port = utils.split_host_port(redis_addr, 6379)
    rds = redis.Redis(host=redis_host, port=redis_port, db=consts.REDIS_KRAKEN_DB)

    # prepare flow summary
    errors = False
    tests_passed = 0
    tests_total = 0
    tests_regr = 0
    tests_fix = 0
    issues_total = 0
    issues_new = 0
    for r in flow.runs:
        if r.jobs_error > 0:
            errors = True
        tests_passed += r.tests_passed
        tests_total += r.tests_total
        tests_regr += r.regr_cnt
        tests_fix += r.fix_cnt
        issues_total += r.issues_total
        issues_new += r.issues_new
    val = dict(id=flow.id,
               label=flow.get_label(),
               errors=errors,
               tests_passed=tests_passed,
               tests_total=tests_total,
               tests_regr=tests_regr,
               tests_fix=tests_fix,
               issues_total=issues_total,
               issues_new=issues_new)

    # store in redis flow state for badge and cctray
    key = 'branch-%d' % flow.branch_id
    val_ext = val.copy()
    val_ext['project'] = flow.branch.project.name
    val_ext['branch'] = flow.branch.name
    val_ext['activity'] = 'Sleeping'
    val_ext['lastBuildTime'] = utils.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    val_ext['url'] = '%s/branches/%d/ci' % (get_setting('general', 'server_url'), flow.branch_id)
    rds.set(key, json.dumps(val_ext))
    log.info('cached flow results: %s = %s', key, val_ext)

    # store in db as well, it will be used for charts in UI,
    flow.summary = val
    db.session.commit()


def analyze_run(run_id):
    log.reset_ctx()
    app = _create_app('analyze_run_%d' % run_id)

    with app.app_context():
        run = Run.query.filter_by(id=run_id).one_or_none()
        if run is None:
            log.error('got unknown run to analyze: %s', run_id)
            return

        log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)
        log.info('starting analysis of run %s', run)

        # calculate run stats
        run.tests_total = run.tests_passed = run.tests_not_run = 0
        run.jobs_error = run.jobs_total = 0
        run.issues_total = 0
        non_covered_jobs = Job.query.filter_by(run=run).filter_by(covered=False).all()
        for job in non_covered_jobs:
            # calculate job tests stats
            for job_tcr in job.results:
                run.tests_total += 1
                if job_tcr.result == consts.TC_RESULT_PASSED:
                    run.tests_passed += 1
                elif job_tcr.result == consts.TC_RESULT_NOT_RUN:
                    run.tests_not_run += 1

            # calculate issues stats
            run.issues_total += len(job.issues)

            # calculate jobs stats
            run.jobs_total += 1
            if job.completion_status not in [consts.JOB_CMPLT_ALL_OK, None]:
                run.jobs_error += 1
            db.session.commit()

        # trigger any following stages to currently completed run if there was no errors
        # and there were some jobs executed (sometimes jobs are not started at all
        # due to some internal problems)
        if run.jobs_error == 0 and run.jobs_total > 0:
            _trigger_stages(run)

        # establish new state for flow
        flow = run.flow
        is_completed = True
        log.info('check if flow %s is completed', flow)
        for r in flow.runs:
            log.info('  run %s: state: %d', r, r.state)
            if r.state == consts.RUN_STATE_IN_PROGRESS:
                is_completed = False
                break
        log.info('flow %s: %s completed', flow, 'IS' if is_completed else 'NOT')

        if is_completed:
            log.info('completed flow %s', flow)
            _prepare_flow_summary(flow)

            now = utils.utcnow()
            flow.finished = now
            flow.state = consts.FLOW_STATE_COMPLETED
            db.session.commit()

        kkrq.enq(analyze_results_history, run.id)
        log.info('run %s analysis completed, started analyze results history', run)


def _analyze_ci_test_case_result(job, job_tcr):
    # log.info('TCR: %s %s %s %s', job_tcr, job_tcr.test_case.name, job_tcr.job.run.flow, job_tcr.job.run.flow.created)

    # get previous 10 results
    q = TestCaseResult.query
    q = q.options(joinedload('comment'))
    q = q.filter(TestCaseResult.id != job_tcr.id)
    q = q.filter_by(test_case_id=job_tcr.test_case_id)
    q = q.join('job')
    q = q.filter_by(covered=False)
    q = q.filter_by(agents_group=job.agents_group)
    q = q.filter_by(system=job.system)
    q = q.join('job', 'run', 'flow', 'branch')
    q = q.filter(Branch.id == job.run.flow.branch_id)
    q = q.filter(Flow.kind == consts.FLOW_KIND_CI)
    q = q.filter(Flow.created < job.run.flow.created)
    q = q.order_by(desc(Flow.created))
    q = q.limit(10)

    # import sqlalchemy.dialects.postgresql
    # s = q.statement.compile(compile_kwargs={"literal_binds": True},
    #                         dialect=sqlalchemy.dialects.postgresql.dialect())
    # log.info(' query: %s', s)

    tcrs = q.all()
    tcrs.reverse() # sort from oldest to latest
    # determine instability and find last test case comment
    tcc = None
    for idx, tcr in enumerate(tcrs):
        # log.info('TCR: %s %s %s', tcr, tcr.test_case.name, tcr.job.run.flow.created)
        if idx == 0:
            job_tcr.instability = 0
        elif tcr.result != tcrs[idx - 1].result:
            job_tcr.instability += 1

        if tcr.comment:
            tcc = tcr.comment

    # if there is no comment in current tcr and there was some in the past, and current result is not passed
    # then assing it to current one
    if not job_tcr.comment and job_tcr.result != consts.TC_RESULT_PASSED:
        if tcc is None:
            q = TestCaseComment.query
            q = q.filter_by(test_case=job_tcr.test_case, branch=job_tcr.job.run.flow.branch)
            tcc = q.one_or_none()
            if tcc:
                # comment was not present in last 10 flows so move it to new state
                tcc.state = consts.TC_COMMENT_NEW
        job_tcr.comment = tcc

        # update last flow in tcc if needed
        if tcc and tcc.last_flow.created < job_tcr.job.run.flow.created:
            tcc.last_flow = job_tcr.job.run.flow

    # determine age and change
    if len(tcrs) > 0:
        prev_tcr = tcrs[-1]
        # log.info('PREV TCR: %s %s %s %s', prev_tcr, prev_tcr.test_case.name, prev_tcr.job.run.flow, prev_tcr.job.run.flow.created)
        if prev_tcr.result == job_tcr.result:
            job_tcr.age = prev_tcr.age + 1
            job_tcr.change = consts.TC_RESULT_CHANGE_NO
            # log.info('PREV TCR: %s no change', prev_tcr)
        else:
            job_tcr.instability += 1
            job_tcr.age = 0
            if job_tcr.result == consts.TC_RESULT_PASSED and prev_tcr.result != consts.TC_RESULT_PASSED:
                job_tcr.change = consts.TC_RESULT_CHANGE_FIX
                # log.info('PREV TCR: %s fix', prev_tcr)
            elif job_tcr.result != consts.TC_RESULT_PASSED and prev_tcr.result == consts.TC_RESULT_PASSED:
                job_tcr.change = consts.TC_RESULT_CHANGE_REGR
                # log.info('PREV TCR: %s regr', prev_tcr)
            # else:
            #     log.info('PREV TCR: %s %s vs %s', prev_tcr, job_tcr.result, prev_tcr.result)
    else:
        # log.info('NO PREV TCR')
        job_tcr.change = consts.TC_RESULT_CHANGE_NEW

    # determine relevancy
    # 0 initial
    job_tcr.relevancy = 0
    # +1 not pass
    if job_tcr.result != consts.TC_RESULT_PASSED:
        job_tcr.relevancy += 1
        # +1 no comment or not root caused comment state
        if not job_tcr.comment or job_tcr.comment.state not in [consts.TC_COMMENT_BUG_IN_PRODUCT, consts.TC_COMMENT_BUG_IN_TEST]:
            job_tcr.relevancy += 1
    # +1 failure
    if job_tcr.result == consts.TC_RESULT_FAILED:
        job_tcr.relevancy += 1
    # +1 instability <= 3
    if job_tcr.instability <= 3:
        job_tcr.relevancy += 1
    # +1 age < 5
    if job_tcr.age < 5:
        job_tcr.relevancy += 1
    # +1 regression (age=0)
    if job_tcr.change == consts.TC_RESULT_CHANGE_REGR:
        job_tcr.relevancy += 1


def _analyze_dev_test_case_result(job, job_tcr):
    # get reference result from CI flow
    q = TestCaseResult.query
    q = q.filter_by(test_case_id=job_tcr.test_case_id)
    q = q.join('job')
    q = q.filter_by(covered=False)
    q = q.filter_by(agents_group=job_tcr.job.agents_group)
    q = q.filter_by(system=job.system)
    q = q.filter_by(state=consts.JOB_STATE_COMPLETED)
    q = q.join('job', 'run', 'flow', 'branch')
    q = q.filter(Branch.id == job.run.flow.branch_id)
    q = q.filter(Flow.kind == consts.FLOW_KIND_CI)
    q = q.order_by(desc(Flow.created))

    ref_tcr = q.first()

    # determine change
    if ref_tcr:
        # log.info('REF TCR: %s %s %s %s', ref_tcr, ref_tcr.test_case.name, ref_tcr.job.run.flow, ref_tcr.job.run.flow.created)
        # copy ref tcr stats to current dev results so user can see how it behaves
        job_tcr.age = ref_tcr.age
        job_tcr.instability = ref_tcr.instability

        if ref_tcr.result == job_tcr.result:
            job_tcr.change = consts.TC_RESULT_CHANGE_NO
        else:
            if job_tcr.result == consts.TC_RESULT_PASSED and ref_tcr.result != consts.TC_RESULT_PASSED:
                job_tcr.change = consts.TC_RESULT_CHANGE_FIX
            elif job_tcr.result != consts.TC_RESULT_PASSED and ref_tcr.result == consts.TC_RESULT_PASSED:
                job_tcr.change = consts.TC_RESULT_CHANGE_REGR
    else:
        log.info('NO REF TCR, ie. new')
        job_tcr.change = consts.TC_RESULT_CHANGE_NEW


def _analyze_job_results_history(job):
    # TODO: if branch is forked from another base branch take base branch results into account

    q = TestCaseResult.query
    q = q.filter_by(job=job)

    counts = [0, 0, 0, 0]
    cnt = 0
    total = 0
    for job_tcr in q.all():
        t0 = time.time()
        # analyze history
        if job.run.flow.kind == consts.FLOW_KIND_CI:
            _analyze_ci_test_case_result(job, job_tcr)
        else:  # DEV
            _analyze_dev_test_case_result(job, job_tcr)

        db.session.commit()

        t1 = time.time()
        total += t1 - t0
        cnt += 1
        log.info('Analyzed result dt:%0.5f %s %s: %s', t1 - t0, job_tcr, job_tcr.test_case.name,
                 consts.TC_RESULT_CHANGES_NAME[job_tcr.change])

        counts[job_tcr.change] += 1

    # current avg time is 0.0295s,
    log.info('Analyzed in time:%0.5f, avg:%0.5f, count:%d',
             total, total / cnt if cnt > 0 else 0, cnt)

    return counts


def _analyze_job_issues_history(job):
    q = Job.query
    q = q.filter_by(name=job.name)
    q = q.filter_by(completion_status=consts.JOB_CMPLT_ALL_OK)
    q = q.filter_by(system=job.system)
    q = q.filter_by(agents_group=job.agents_group)
    q = q.join('run')
    q = q.filter_by(stage=job.run.stage)
    q = q.join('run', 'flow')
    q = q.filter(Flow.created < job.run.flow.created)
    q = q.filter(Flow.kind == consts.FLOW_KIND_CI)
    q = q.order_by(desc(Flow.created))
    prev_job = q.first()
    if prev_job is None:
        log.info('prev job for issues not found')
        return 0

    issues_new = 0

    for issue in job.issues:
        log.info('Analyze issue %s', issue)
        prev_issue = None
        dist = 1000
        log.info('PREV ISSES %s', len(prev_job.issues))
        for i in prev_job.issues:
            if i.path != issue.path or i.issue_type != issue.issue_type or i.symbol !=issue.symbol:
                continue
            new_dist = abs(i.line - issue.line)
            if new_dist > 5:
                continue
            log.info('issue %s - prev issue %s, dist %s', issue, i, new_dist)
            if new_dist < dist:
                dist = new_dist
                prev_issue = i

        if prev_issue is not None:
            issue.age = prev_issue.age + 1
        if issue.age == 0:
            issues_new += 1
    db.session.commit()

    return issues_new


def _analyze_results_history(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        log.error('got unknown run to analyze results history: %s', run_id)
        return

    log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

    log.info('starting results history analysis of run %s, flow %s [%s] ',
             run, run.flow, 'CI' if run.flow.kind == 0 else 'DEV')

    # check prev run in case of CI
    if run.flow.kind == 0:
        q = Run.query
        q = q.filter_by(deleted=None)
        q = q.filter_by(stage_id=run.stage_id)
        q = q.join('flow')
        q = q.filter(Flow.created < run.flow.created)
        q = q.filter(Flow.kind == run.flow.kind)
        q = q.order_by(desc(Flow.created))
        prev_run = q.first()
        if prev_run is None:
            log.info('this is the first run %s in the first flow %s of branch %s',
                     run, run.flow, run.flow.branch)

        elif prev_run.state not in [consts.RUN_STATE_PROCESSED, consts.RUN_STATE_MANUAL]:
            # prev run is not processed yet
            log.info('postpone anlysis of run %s as prev run %s is not processed yet', run, prev_run)
            return

    # analyze jobs history of this run
    run.new_cnt = run.no_change_cnt = run.regr_cnt = run.fix_cnt = 0
    run.issues_new = 0
    non_covered_jobs = Job.query.filter_by(run=run).filter_by(covered=False).all()
    for job in non_covered_jobs:
        log.set_ctx(job=job.id)
        # analyze results history
        counts = _analyze_job_results_history(job)
        no_change_cnt, fix_cnt, regr_cnt, new_cnt = counts
        run.no_change_cnt += no_change_cnt
        run.fix_cnt += fix_cnt
        run.regr_cnt += regr_cnt
        run.new_cnt += new_cnt
        db.session.commit()

        # analyze issues history
        issues_new = _analyze_job_issues_history(job)
        run.issues_new += issues_new
        db.session.commit()
        # log.info('job %s: new:%d no-change:%d regr:%d fix:%d',
        #          job, new_cnt, no_change_cnt, regr_cnt, fix_cnt)
    log.set_ctx(job=None)

    log.info('run %s: new:%d no-change:%d regr:%d fix:%d',
             run, run.new_cnt, run.no_change_cnt, run.regr_cnt, run.fix_cnt)

    run.state = consts.RUN_STATE_PROCESSED
    run.processed_at = utils.utcnow()
    db.session.commit()
    log.info('history anlysis of run %s completed', run)

    kkrq.enq(notify_about_completed_run, run.id)

    # trigger analysis of the following run
    q = Run.query
    q = q.filter_by(stage_id=run.stage_id)
    q = q.join('flow')
    q = q.filter(Flow.created > run.flow.created)
    q = q.filter(Flow.kind == run.flow.kind)
    q = q.order_by(asc(Flow.created))
    next_run = q.first()
    if next_run is not None and next_run.state in [consts.RUN_STATE_COMPLETED, consts.RUN_STATE_PROCESSED]:
        kkrq.enq_neck(analyze_results_history, next_run.id)

    log.info('finished results history analysis of run %s, flow %s [%s]',
             run, run.flow, 'CI' if run.flow.kind == 0 else 'DEV')


def analyze_results_history(run_id):
    log.reset_ctx()
    app = _create_app('analyze_results_history_%d' % run_id)

    with app.app_context():
        _analyze_results_history(run_id)


def notify_about_started_run(run_id):
    log.reset_ctx()
    app = _create_app('notify_about_started_run_%d' % run_id)

    with app.app_context():
        run = Run.query.filter_by(id=run_id).one_or_none()
        if run is None:
            log.error('got unknown run to notify: %s', run_id)
            return

        log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)
        log.info('starting notification about started run %s', run)

        notify.notify(run, 'start')


def notify_about_completed_run(run_id):
    log.reset_ctx()
    app = _create_app('notify_about_completed_run_%s' % run_id)

    with app.app_context():
        run = Run.query.filter_by(id=run_id).one_or_none()
        if run is None:
            log.error('got unknown run to notify: %s', run_id)
            return

        log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)
        log.info('starting notification about completed run %s', run)

        notify.notify(run, 'end')


def _estimate_timeout(job):
    if not job.assigned or not job.finished:
        log.warning('job %s has None dates: %s %s', job, job.assigned, job.finished)
        return
    if job.assigned > job.finished:
        log.warning('job %s has wrong dates: %s %s', job, job.assigned, job.finished)
        return

    q = Job.query
    q = q.filter_by(name=job.name)
    q = q.filter_by(state=consts.JOB_STATE_COMPLETED)
    q = q.filter(Job.completion_status.in_([consts.JOB_CMPLT_ALL_OK, consts.JOB_CMPLT_JOB_TIMEOUT]))
    q = q.filter_by(covered=False)
    q = q.filter_by(agents_group=job.agents_group)
    q = q.filter_by(system=job.system)
    # TODO add filtering by config
    q = q.join('run')
    q = q.filter(Run.stage_id == job.run.stage_id)
    q = q.join('run', 'flow')
    q = q.filter(Flow.created <= job.run.flow.created)
    q = q.order_by(desc(Flow.created))
    q = q.limit(10)

    jobs = q.all()
    if len(jobs) < 4:
        log.info('not enough jobs to estimate timeout')
        return

    # check job timestamps
    if not job.assigned:
        log.info('job %s assigned in None', job)
    if not job.finished:
        log.info('job %s finished in None', job)
    if job.assigned > job.finished:
        log.info('job %s assigned %s > finished %s', job, job.assigned, job.finished)
    if not job.assigned or not job.finished or job.assigned > job.finished:
        max_duration = duration = consts.DEFAULT_JOB_TIMEOUT
    else:
        max_duration = duration = job.finished - job.assigned

    # find max duration in last 10 jobs
    timeout_occured = False
    prev_job_id = job.id
    for j in jobs:
        if not j.assigned or not j.finished:
            log.warning('job %s has None dates: %s %s', j, j.assigned, j.finished)
            continue
        if j.assigned > j.finished:
            log.warning('job %s has wrong dates: %s %s', j, j.assigned, j.finished)
            continue
        if j.completion_status == consts.JOB_CMPLT_JOB_TIMEOUT:
            timeout_occured = True

        if j.id == prev_job_id:
            # cumulate duration if this is the same job (TODO: why?)
            duration += j.finished - j.assigned
        else:
            duration = j.finished - j.assigned
            prev_job_id = j.id

        if duration > max_duration:
            max_duration = duration

    # estimate new timeout from max duration
    timeout = int(max_duration.total_seconds() * 1.7)
    timeout = max(timeout, 60)

    stage = job.run.stage
    job_key = "%s-%d-%d" % (job.name, job.system_id, job.agents_group_id)

    if stage.timeouts is None:
        stage.timeouts = {}

    # if timeout occured in last 10 jobs than make new timeout adjustment
    if timeout_occured:
        old_timeout = stage.timeouts.get(job_key, consts.DEFAULT_JOB_TIMEOUT)
        log.info('new: %s, old: %s', timeout, old_timeout)
        if timeout < old_timeout:
            timeout = old_timeout * 2

        for j in stage.schema['jobs']:
            if j['name'] == job.name:
                user_timeout = j.get('timeout', consts.DEFAULT_JOB_TIMEOUT)
                break

        log.info('new: %s, user: %s', timeout, user_timeout)
        timeout = max(timeout, user_timeout)

    # it does not make sense to make timeout bigger than 3 days ie. 259200 seconds
    timeout = max(timeout, 259200)

    log.info("new timeout for job '%s' in stage '%s': %ssecs", job_key, stage.name, timeout)
    stage.timeouts[job_key] = timeout
    flag_modified(stage, 'timeouts')
    db.session.commit()


def job_completed(job_id):
    log.reset_ctx()
    app = _create_app('job_completed_%d' % job_id)

    with app.app_context():

        now = utils.utcnow()

        job = Job.query.filter_by(id=job_id).one_or_none()
        if job is None:
            log.error('got unknown job: %s', job_id)
            return

        log.set_ctx(branch=job.run.flow.branch_id, flow_kind=job.run.flow.kind, flow=job.run.flow_id, run=job.run_id, job=job.id)
        log.info('completing job %s', job)

        if job.state != consts.JOB_STATE_COMPLETED:
            job.completed = now
            job.state = consts.JOB_STATE_COMPLETED
            job.completion_status = consts.JOB_CMPLT_ALL_OK
            log.info('checking steps')
            for step in job.steps:
                log.info('%s: %s', step.index, consts.STEP_STATUS_NAME[step.status] if step.status in consts.STEP_STATUS_NAME else step.status)
                if step.status == consts.STEP_STATUS_ERROR:
                    # set base cmplt status error
                    job.completion_status = consts.JOB_CMPLT_AGENT_ERROR_RETURNED
                    # set proper cmplt status based on reason
                    if step.result and 'reason' in step.result:
                        if step.result['reason'] == 'job-timeout':
                            job.completion_status = consts.JOB_CMPLT_JOB_TIMEOUT
                        if step.result['reason'] == 'step-timeout':
                            job.completion_status = consts.JOB_CMPLT_STEP_TIMEOUT
                        elif step.result['reason'] == 'exception':
                            job.completion_status = consts.JOB_CMPLT_AGENT_EXCEPTION
                    break
            db.session.commit()

            _estimate_timeout(job)

        # establish new run state
        run = job.run
        is_completed = True
        for j in run.jobs:
            if j.state != consts.JOB_STATE_COMPLETED:
                is_completed = False
                break

        if is_completed:
            exec_utils.complete_run(run, now)


def _check_repo_commits(stage, flow_kind):
    triggers = stage.schema['triggers']
    if 'repo' not in triggers:
        return True, None  # no repo in triggers so start run; no repo_data

    # get prev run to get prev commit
    prev_run = dbutils.get_prev_run(stage.id, flow_kind)

    log.info('looking for new commits for stage %s, prev run %s', stage, prev_run)

    repo = triggers['repo']
    repos = []
    if 'url' in repo:
        repos.append((repo['url'], repo['branch']))
    else:
        for r in repo['repos']:
            repos.append((r['url'], r['branch']))

    git_cfg = repo.get('git_cfg', {})

    # iterate over repos
    changes = False
    repo_data = []
    for repo_url, repo_branch in repos:
        commits, base_commit = gitops.get_repo_commits_since(stage.branch_id, prev_run, repo_url, repo_branch, git_cfg)

        if commits:
            changes = True
            after = commits[0]['id']
        else:
            after = base_commit
        repo_data.append(dict(repo=repo_url,
                              commits=commits,
                              before=base_commit,
                              after=after,
                              trigger='git-push'))

    if not changes:
        log.info('no commits since prev check')
    else:
        log.info('detected commits since prev check')
    return changes, repo_data


def trigger_run(stage_id, flow_kind=consts.FLOW_KIND_CI, reason=None):
    log.reset_ctx()
    app = _create_app('trigger_run_%d' % stage_id)

    with app.app_context():
        stage = Stage.query.filter_by(id=stage_id).one_or_none()
        if stage is None:
            log.error('got unknown stage: %s', stage_id)
            return

        log.set_ctx(branch=stage.branch_id, flow_kind=flow_kind)
        log.info('triggering run for stage %s, flow kind %d', stage, flow_kind)

        # if this stage does not have parent then start new flow
        new_flow = False
        if stage.schema['parent'] == 'root':
            flow = Flow(branch=stage.branch, kind=flow_kind)
            new_flow = True

            # TODO: other root, sibling stages should be triggered when new flow is started

        else:
            # if this stage has parent then find latest flow with this parent stage run

            # first find parent stage using its name
            q = Stage.query.filter_by(name=stage.schema['parent'])
            q = q.filter_by(deleted=None)
            q = q.filter_by(branch_id=stage.branch_id)
            parent_stage = q.one_or_none()
            if parent_stage is None:
                log.error('parent stage %s for stage %s is missing', stage.schema['parent'], stage)
                return

            # find latest run of parent stage
            q = Run.query
            q = q.filter_by(deleted=None)
            q = q.filter_by(stage_id=parent_stage.id)
            q = q.join('flow')
            q = q.filter(Flow.kind == flow_kind)
            q = q.order_by(desc(Flow.created))
            parent_run = q.first()
            if parent_run is None:
                log.info('no run for parent stage %s', parent_stage)
                return

            # find if there is no run for current stage
            q = Run.query
            q = q.filter_by(deleted=None)
            q = q.filter_by(stage_id=stage.id)
            q = q.filter_by(flow_id=parent_run.flow_id)
            run = q.first()
            if run is not None:
                # TODO: in such case this trigger should be postponed to new flow
                log.info('latest flow %s with parent run %s already has run %s for current stage %s',
                         parent_run.flow_id, parent_run, run, stage)
                return

            flow = parent_run.flow

        # if the trigger is repo then first check if there were any new commits to the repo
        changes, repo_data = _check_repo_commits(stage, flow_kind)
        if not changes:
            return
        if repo_data:
            repo_data = RepoChanges(data=repo_data)
        if repo_data and reason and reason['reason'] == 'repo_interval':
            reason = dict(reason='commit to repo')
        if repo_data and new_flow:
            flow.trigger_data = repo_data

        # commit new flow if created and repo changes if detected
        db.session.commit()

        log.set_ctx(flow=flow.id)

        # create run for current stage
        if reason is None:
            reason = dict(reason='unknown')
        exec_utils.start_run(stage, flow, reason=reason, repo_data=repo_data)


def trigger_flow(project_id, trigger_data=None):
    log.reset_ctx()
    app = _create_app('trigger_flow_%d' % project_id)

    with app.app_context():
        project = Project.query.filter_by(id=project_id).one_or_none()
        if project is None:
            log.error('got unknown project: %s', project_id)
            return
        log.info('triggering flow for project %s', project)

        if trigger_data['trigger'] in ['github-push', 'gitea-push', 'gitlab-Push Hook']:
            branch_name = trigger_data['ref'].split('/')[-1]
            flow_kind = 'ci'
            flow_kind_no = 0
        elif trigger_data['trigger'] in ['github-pull_request', 'gitea-pull_request', 'gitlab-Merge Request Hook']:
            branch_name = trigger_data['pull_request']['base']['ref']
            flow_kind = 'dev'
            flow_kind_no = 1
        else:
            log.error('unsupported trigger %s', trigger_data['trigger'])
            return

        reason = trigger_data['trigger'].replace('-', ' ').replace('_', ' ')
        reason = reason.replace('Hook', '').strip()
        reason = dict(reason=reason)

        branch = Branch.query.filter_by(project=project, branch_name=branch_name).one_or_none()
        if branch is None:
            log.warning('cannot find branch by branch_name: %s', branch_name)
            return

        log.set_ctx(branch=branch.id)

        q = Flow.query
        q = q.filter_by(branch=branch)
        q = q.filter_by(kind=flow_kind_no)
        q = q.order_by(desc(Flow.created))
        last_flow = q.first()

        # handle the case when this is the first flow in the branch
        if last_flow is None:
            exec_utils.create_a_flow(branch, flow_kind, {})
            return

        trigger_git_url = trigger_data['repo']
        try:
            url = giturlparse.parse(trigger_git_url)
            trigger_git_url = url.url2https
        except Exception:
            log.warning('cannot parse trigger git url: %s', trigger_git_url)

        # find stages that use repo from trigger
        matching_stages = []
        for stage in branch.stages:
            if stage.deleted:
                continue
            found = False
            for job in stage.schema['jobs']:
                for step in job['steps']:
                    if step['tool'] == 'git':
                        git_url = step['checkout']
                        try:
                            url = giturlparse.parse(git_url)
                            git_url = url.url2https
                        except Exception:
                            # TODO: git url should be checked upfront and errors reported to user
                            log.warning('cannot parse git url: %s', git_url)
                            continue
                        if git_url == trigger_git_url:
                            matching_stages.append(stage)
                            found = True
                            break
                if found:
                    break

        # map runs to stages
        run_stages = {run.stage_id: run for run in last_flow.runs if not run.deleted}
        name_stages = {stage.name: stage for stage in branch.stages if not stage.deleted}

        # change trigger_data into db record
        trigger_data = RepoChanges(data=[trigger_data])

        # for stages that were not run while their parent was run, do run them now
        started_something = False
        for stage in matching_stages:
            if stage.id in run_stages:
                # TODO: trigger new flow?
                continue
            if not stage.enabled:
                log.info('stage %s not started - disabled', stage)
                continue
            parent_name = stage.schema['parent']
            if parent_name != 'root':
                parent_stage = name_stages[parent_name]
                if parent_stage.id not in run_stages:
                    # TODO: we should wait when parent is run and then trigger this stage
                    continue

            if not last_flow.trigger_data:
                last_flow.trigger_data = trigger_data
                db.session.commit()

            exec_utils.start_run(stage, last_flow, reason=reason)
            started_something = True

        if not started_something:
            exec_utils.create_a_flow(branch, flow_kind, {}, trigger_data)


def refresh_schema_repo(stage_id, complete_starting_run_id=None):
    log.reset_ctx()
    app = _create_app('refresh_schema_repo_%d' % stage_id)

    with app.app_context():
        stage = Stage.query.filter_by(id=stage_id).one_or_none()
        if stage is None:
            log.error('got unknown stage: %s', stage_id)
            return

        log.set_ctx(branch=stage.branch_id)
        run = None
        if complete_starting_run_id:
            run = Run.query.filter_by(id=complete_starting_run_id).one_or_none()
            if run is not None:
                log.set_ctx(flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

        log.info('refresh schema repo for stage: %s, run: %s',
                 stage, run)

        planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
        planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)

        # cancel any previous scheduled refresh job
        if stage.repo_refresh_job_id:
            planner.remove_job(stage.repo_refresh_job_id)
            stage.repo_refresh_job_id = ''
            db.session.commit()

        try:
            # get schema from repo
            if stage.repo_access_token:
                secret = Secret.query.filter_by(project=stage.branch.project, name=stage.repo_access_token).one()
                repo_access_token = secret.data['secret']
            else:
                repo_access_token = None

            schema_code, version = gitops.get_schema_from_repo(stage.repo_url, stage.repo_branch, repo_access_token,
                                                               stage.schema_file, stage.git_clone_params)

            # check schema
            ctx = prepare_context(stage, stage.get_default_args())
            schema_code, schema = check_and_correct_stage_schema(stage.branch, stage.name, schema_code, ctx)
        except Exception as e:
            stage.repo_error = str(e)
            stage.repo_state = consts.REPO_STATE_ERROR
            db.session.commit()
            log.exception('problem with schema, stage: %d, run: %s',
                          stage_id, complete_starting_run_id)
            return

        # store schema id db
        prev_triggers = stage.schema['triggers']
        stage.schema = schema
        flag_modified(stage, 'schema')
        stage.schema_code = schema_code
        stage.repo_state = consts.REPO_STATE_OK
        stage.repo_error = ''
        stage.repo_version = version
        stage.schema_from_repo_enabled = True
        if stage.triggers is None:
            stage.triggers = {}
        prepare_new_planner_triggers(stage.id, schema['triggers'], prev_triggers, stage.triggers)
        flag_modified(stage, 'triggers')
        log.info('stage: %s, new schema: %s', stage, stage.schema)

        # start schema refresh job
        try:
            interval = int(stage.repo_refresh_interval)
        except Exception:
            interval = int(pytimeparse.parse(stage.repo_refresh_interval))
        job = planner.add_job('kraken.server.pljobs:refresh_schema_repo', 'interval', (stage_id,), None,
                              None, None, None, None, None, None, False, dict(seconds=interval))

        stage.repo_refresh_job_id = job['id']
        db.session.commit()

        if complete_starting_run_id:
            exec_utils.complete_starting_run(complete_starting_run_id)


def spawn_new_agents(agents_group_id):
    log.reset_ctx()
    app = _create_app('spawn_new_agents_%d' % agents_group_id)

    with app.app_context():
        server_url = get_setting('general', 'server_url')
        clickhouse_addr = get_setting('general', 'clickhouse_addr')
        settings = ['server_url', 'clickhouse_addr']
        for s in settings:
            val = locals()[s]
            if not val:
                log.error('%s is empty, please set it in global general settings', s)
                return

        ag = AgentsGroup.query.filter_by(id=agents_group_id).one_or_none()
        if ag is None:
            log.warning('cannot find agents group id: %d', agents_group_id)
            return

        try:
            _, depl = ag.get_deployment()
        except Exception:
            log.exception('IGNORED EXCEPTION')
            return

        # check if limit of agents is reached
        q = Agent.query.filter_by(authorized=True, disabled=False, deleted=None)
        q = q.join('agents_groups')
        q = q.filter_by(agents_group=ag)
        agents_count = q.count()
        limit = depl.get('instances_limit', 0)
        if agents_count >= limit:
            log.warning('in agents group id:%d cannot spawn more agents, limit %d reached', agents_group_id, limit)
            return

        # find waiting jobs assigned to this agents group
        jobs = defaultdict(int)
        q = Job.query.filter_by(covered=False, deleted=None, state=consts.JOB_STATE_QUEUED)
        q = q.filter_by(agents_group=ag)
        for job in q.all():
            sys_id = job.system_id if job.system.executor == 'local' else 0
            jobs[sys_id] += 1

        # go through systems needed and the counts and spawn agents
        for sys_id, needed_count in jobs.items():
            log.info('agents group %d, system id %d: needed %d', agents_group_id, sys_id, needed_count)

            # find system info
            if sys_id != 0:
                system = System.query.filter_by(id=sys_id).one_or_none()
                if system is None:
                    log.warning('cannot find system id:%d', sys_id)
                    continue
            else:
                system = System.query.filter_by(name=depl['default_image']).one_or_none()
                if system is None:
                    log.warning('cannot find system id:%d', sys_id)
                    continue

            # check if there is enough agents with proper system
            q = Agent.query.filter_by(authorized=True, disabled=False, deleted=None)
            q = q.join('agents_groups')
            q = q.filter_by(agents_group=ag)
            agents = q.all()
            agents_count = 0
            # log.info('potential agents num: %d', len(agents))
            for a in agents:
                if a.extra_attrs and 'system' in a.extra_attrs and a.extra_attrs['system'] == sys_id:
                    agents_count += 1
            num = needed_count - agents_count
            if num <= 0:
                log.info('enough agents, avail: %d, needed: %d', agents_count, needed_count)
                continue
            log.info('NOT enough agents, avail: %d, needed: %d, new: %d', agents_count, needed_count, num)

            cloud.create_machines(ag, system, num,
                                  server_url, clickhouse_addr)


def destroy_machine(agent_id):
    log.reset_ctx()
    app = _create_app('destroy_machine_%s' % agent_id)

    with app.app_context():
        agent = Agent.query.filter_by(id=int(agent_id)).one_or_none()
        if agent is None:
            log.error('cannot find agent id:%d', agent_id)
            return

        if not agent.extra_attrs:
            log.warning('missing extra_attrs in agent %s', agent)
            dbutils.delete_agent(agent)
            return

        ag = dbutils.find_cloud_assignment_group(agent)
        if not ag:
            log.error('agent %s does not have cloud group', agent)
            dbutils.delete_agent(agent)
            return

        dbutils.delete_agent(agent)

        cloud.destroy_machine(ag, agent)


def load_remote_tool(tool_id):
    log.reset_ctx()
    app = _create_app('load_remote_tool_%s' % tool_id)

    with app.app_context():
        tool_id = int(tool_id)
        tool = Tool.query.filter_by(id=tool_id).one_or_none()
        if tool is None:
            log.error('cannot find tool id:%d', tool_id)
            return

        # clone tool from remote repo
        try:
            tmpdir, repo_dir, version = gitops.clone_tool_repo(tool.url, tool.tag, tool_id)
        except Exception:
            log.exception('problem with cloning repo')
            return

        tf = None
        try:
            # package tool
            tool_file_path = os.path.join(repo_dir, tool.tool_file)
            if not os.path.exists(tool_file_path):
                log.warning('Tool meta file %s does not exist in repo %s', tool.tool_file, tool.url)
                return

            meta, tf, _ = toolops.package_tool(tool_file_path)

            name = meta['name']
            description = meta['description']
            location = meta['location']
            entry = meta['entry']
            fields = meta['parameters']

            # check if tool schema is ok
            toolutils.check_tool_schema(fields)

            if tool.version == tool.tag:
                # initial tool so set the fields from meta
                tool.name = name
                tool.description = description
                tool.version = version
                tool.location = location
                tool.entry = entry
                tool.fields = fields
            elif tool.version != version:
                # new version of tool so create new tool record in db
                tool = Tool(name=name, description=description, version=version, location=location, entry=entry, fields=fields)
                db.session.flush()
            elif tool.version == version:
                log.info('Tool %s name:%s from remote repo %s @ %s does not need to updated, the same version %s',
                         tool, tool.name, tool.url, tool.tag, version)

            # store tool
            toolutils.store_tool_in_minio(tf, tool)
            db.session.commit()

            log.info('Stored tool %s name:%s from remote repo %s @ %s', tool, tool.name, tool.url, tool.tag)

        finally:
            if tf:
                tf.close()
            tmpdir.cleanup()
