# Copyright 2020 The Kraken Authors
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
import datetime
import tempfile
import subprocess
import xmlrpc.client

from celery import Task
from flask import Flask
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified
import giturlparse
import pytimeparse

from .clry import app as clry_app
from ..models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project
from ..schema import prepare_new_planner_triggers, get_schema_from_repo
from ..schema import check_and_correct_stage_schema
from .. import execution  # pylint: disable=cyclic-import
from .. import consts
from .. import notify
from .. import logs
from .. import dbutils

log = logging.getLogger(__name__)


def _create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)

    logs.setup_logging('celery')

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


class BaseTask(Task):  # pylint: disable=abstract-method
    def on_success(self, retval, task_id, args, kwargs):
        #  Notify user with email
        log.info('ALL OK %s', self.name)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        #  Log unsuccessful login
        log.info('PROBLEMS')


def _trigger_stages(run):
    """Trigger the following stages after just completed run_id stage."""
    log.info('starting triggering stages after run %s', run.id)

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
            execution.start_run(stage, run.flow, reason=dict(reason='parent', run_id=run.id))
        else:
            log.info('stage %s not started because it is disabled', stage.name)


@clry_app.task(base=BaseTask, bind=True)
def analyze_run(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting analysis of run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to analyze: %s', run_id)
                return

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
            if run.jobs_error == 0:
                _trigger_stages(run)

            # establish new state for flow
            flow = run.flow
            is_completed = True
            for r in flow.runs:
                if r.state == consts.RUN_STATE_IN_PROGRESS:
                    is_completed = False
                    break

            if is_completed:
                log.info('completed flow %s', flow)
                now = datetime.datetime.utcnow()
                flow.finished = now
                flow.state = consts.FLOW_STATE_COMPLETED
                db.session.commit()

            t = analyze_results_history.delay(run.id)
            log.info('run %s analysis completed, started analyze results history: %s', run, t)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


def _analyze_job_results_history(job):
    # TODO: if branch is forked from another base branch take base branch results into account

    # history stats
    new_cnt = 0
    no_change_cnt = 0
    regr_cnt = 0
    fix_cnt = 0

    for job_tcr in job.results:
        # analyze history
        log.info('Analyze result %s %s', job_tcr, job_tcr.test_case.name)

        # CI flow: either get previous 10 results
        if job.run.flow.kind == 0:  # CI
            q = TestCaseResult.query
            q = q.filter(TestCaseResult.id != job_tcr.id)
            q = q.filter_by(test_case_id=job_tcr.test_case_id)
            q = q.join('job')
            q = q.filter_by(covered=False)
            q = q.filter_by(agents_group=job_tcr.job.agents_group)
            q = q.filter_by(system=job.system)
            q = q.join('job', 'run', 'flow', 'branch')
            q = q.filter(Branch.id == job.run.flow.branch_id)
            q = q.filter(Flow.kind == 0)  # CI
            q = q.filter(Flow.created < job.run.flow.created)
            q = q.order_by(desc(Flow.created))
            q = q.limit(10)

            tcrs = q.all()
            tcrs.reverse() # sort from oldest to latest
            # determine instability
            for idx, tcr in enumerate(tcrs):
                log.info('TCR: %s %s %s', tcr, tcr.test_case.name, tcr.job.run.flow.created)
                if idx == 0:
                    job_tcr.instability = 0
                elif tcr.result != tcrs[idx - 1].result:
                    job_tcr.instability += 1

            # determine age and change
            if len(tcrs) > 0:
                prev_tcr = tcrs[-1]
                if prev_tcr.result == job_tcr.result:
                    job_tcr.age = prev_tcr.age + 1
                    no_change_cnt += 1
                else:
                    job_tcr.instability += 1
                    job_tcr.age = 0
                    if job_tcr.result == consts.TC_RESULT_PASSED and prev_tcr.result != consts.TC_RESULT_PASSED:
                        job_tcr.change = consts.TC_RESULT_CHANGE_FIX
                        fix_cnt += 1
                    elif job_tcr.result != consts.TC_RESULT_PASSED and prev_tcr.result == consts.TC_RESULT_PASSED:
                        job_tcr.change = consts.TC_RESULT_CHANGE_REGR
                        regr_cnt += 1
            else:
                job_tcr.change = consts.TC_RESULT_CHANGE_NEW
                new_cnt += 1

        # DEV flow: get reference result from CI flow
        else:
            q = TestCaseResult.query
            q = q.filter_by(test_case_id=job_tcr.test_case_id)
            q = q.join('job')
            q = q.filter_by(covered=False)
            q = q.filter_by(agents_group=job_tcr.job.agents_group)
            q = q.filter_by(system=job.system)
            q = q.filter_by(state=consts.JOB_STATE_COMPLETED)
            q = q.join('job', 'run', 'flow', 'branch')
            q = q.filter(Branch.id == job.run.flow.branch_id)
            q = q.filter(Flow.kind == 0)  # CI
            q = q.order_by(desc(Flow.created))

            ref_tcr = q.first()
            log.info('REF TCR: %s %s %s %s', ref_tcr, ref_tcr.test_case.name, ref_tcr.job.run.flow, ref_tcr.job.run.flow.created)

            # determine change
            if ref_tcr:
                if ref_tcr.result == job_tcr.result:
                    no_change_cnt += 1
                else:
                    if job_tcr.result == consts.TC_RESULT_PASSED and ref_tcr.result != consts.TC_RESULT_PASSED:
                        job_tcr.change = consts.TC_RESULT_CHANGE_FIX
                        fix_cnt += 1
                    elif job_tcr.result != consts.TC_RESULT_PASSED and ref_tcr.result == consts.TC_RESULT_PASSED:
                        job_tcr.change = consts.TC_RESULT_CHANGE_REGR
                        regr_cnt += 1
            else:
                job_tcr.change = consts.TC_RESULT_CHANGE_NEW
                new_cnt += 1

        db.session.commit()

    return new_cnt, no_change_cnt, regr_cnt, fix_cnt


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
    q = q.filter(Flow.kind == 0)  # CI
    q = q.order_by(desc(Flow.created))
    prev_job = q.first()
    if prev_job is None:
        log.info('prev job not found')
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


@clry_app.task(base=BaseTask, bind=True)
def analyze_results_history(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to analyze results history: %s', run_id)
                return

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
                    log.info('skip anlysis of run %s as there is no prev run', run)
                    return
                if prev_run.state == consts.RUN_STATE_IN_PROGRESS:
                    # prev run is not completed yet
                    log.info('postpone anlysis of run %s as prev run %s is not completed yet', run, prev_run)
                    return

            # analyze jobs of this run
            run.new_cnt = run.no_change_cnt = run.regr_cnt = run.fix_cnt = 0
            run.issues_new = 0
            non_covered_jobs = Job.query.filter_by(run=run).filter_by(covered=False).all()
            for job in non_covered_jobs:
                log.set_ctx(job=job.id)
                # analyze results history
                counts = _analyze_job_results_history(job)
                new_cnt, no_change_cnt, regr_cnt, fix_cnt = counts
                run.new_cnt += new_cnt
                run.no_change_cnt += no_change_cnt
                run.regr_cnt += regr_cnt
                run.fix_cnt += fix_cnt
                db.session.commit()

                # analyze issues history
                issues_new = _analyze_job_issues_history(job)
                run.issues_new += issues_new
                db.session.commit()
            log.set_ctx(job=None)

            run.state = consts.RUN_STATE_PROCESSED
            db.session.commit()
            log.info('history anlysis of run %s completed', run)

            t = notify_about_completed_run.delay(run.id)
            log.info('enqueued notification about completion of run %s, bg processing: %s', run, t)

            # trigger analysis of the following run
            q = Run.query
            q = q.filter_by(stage_id=run.stage_id)
            q = q.join('flow')
            q = q.filter(Flow.created > run.flow.created)
            q = q.filter(Flow.kind == run.flow.kind)
            q = q.order_by(asc(Flow.created))
            next_run = q.first()
            if next_run is not None and next_run.state in [consts.RUN_STATE_COMPLETED, consts.RUN_STATE_PROCESSED]:
                t = analyze_results_history.delay(next_run.id)
                log.info('enqueued anlysis of run %s, bg processing: %s', next_run, t)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def notify_about_started_run(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting notification about started run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to notify: %s', run_id)
                return

            notify.notify(run, 'start')

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def notify_about_completed_run(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting notification about completed run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to notify: %s', run_id)
                return

            notify.notify(run, 'end')

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


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
    if timeout < 60:
        timeout = 60

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
        if timeout < user_timeout:
            timeout = user_timeout

    log.info("new timeout for job '%s' in stage '%s': %ssecs", job_key, stage.name, timeout)
    stage.timeouts[job_key] = timeout
    flag_modified(stage, 'timeouts')
    db.session.commit()


@clry_app.task(base=BaseTask, bind=True)
def job_completed(self, job_id):
    try:
        app = _create_app()

        with app.app_context():

            now = datetime.datetime.utcnow()

            log.info('completing job %s', job_id)
            job = Job.query.filter_by(id=job_id).one_or_none()
            if job is None:
                log.error('got unknown job: %s', job_id)
                return

            log.set_ctx(job=job_id)

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
                execution.complete_run(run, now)

    except Exception as exc:
        log.exception('will retry')
        log.set_ctx(job=None)
        raise self.retry(exc=exc)

    log.set_ctx(job=None)


def _check_repo_commits(stage, flow_kind):
    triggers = stage.schema['triggers']
    if 'repo' not in triggers:
        return True, None  # no repo in triggers so start run; no repo_data

    # get prev run to get prev commit
    prev_run = dbutils.get_prev_run(stage.id, flow_kind)

    log.info('looking for new commits for stage %s, prev run %s', stage.name, prev_run)

    repo = triggers['repo']
    repos = []
    if 'url' in repo:
        repos.append((repo['url'], repo['branch']))
    else:
        for r in repo['repos']:
            repos.append((r['url'], r['branch']))

    changes = False
    repo_data = {}
    for repo_url, repo_branch in repos:
        commits = []
        log.info('checking commits in %s %s', repo_url, repo_branch)
        with  tempfile.TemporaryDirectory(prefix='kraken-git-') as tmpdir:
            # clone repo
            cmd = "git clone --single-branch --branch %s '%s' repo" % (repo_branch, repo_url)
            p = subprocess.run(cmd, shell=True, check=False, cwd=tmpdir, capture_output=True, text=True)
            if p.returncode != 0:
                err = "command '%s' returned non-zero exit status %d\n" % (cmd, p.returncode)
                err += p.stdout.strip()[:140] + '\n'
                err += p.stderr.strip()[:140]
                err = err.strip()
                raise Exception(err)

            repo_dir = os.path.join(tmpdir, 'repo')

            # get commits history
            cmd = "git log --no-merges --since='2 weeks ago' -n 20 --pretty=format:'commit:%H%nauthor:%an%nemail:%ae%ndate:%aI%nsubject:%s'"
            if prev_run and prev_run.repo_data and repo_url in prev_run.repo_data:
                base_commit = prev_run.repo_data[repo_url][0]['commit']
                log.info('base commit: %s', base_commit)
                cmd += ' %s..' % base_commit
            else:
                log.info('no base commit %s %s', repo_url, prev_run.repo_data)
            p = subprocess.run(cmd, shell=True, check=True, cwd=repo_dir, capture_output=True, text=True)
            text = p.stdout.strip()

            commit = {}
            for line in text.splitlines():
                field, val = line.split(':', 1)
                commit[field] = val
                if len(commit) == 5:
                    commits.append(commit)
                    log.info('  %s', commit)
                    commit = {}
        if commits:
            changes = True
        repo_data[repo_url] = commits

    if not changes:
        log.info('no commits since prev check')
    return changes, repo_data


@clry_app.task(base=BaseTask, bind=True)
def trigger_run(self, stage_id, flow_kind=consts.FLOW_KIND_CI, reason=None):
    try:
        app = _create_app()

        with app.app_context():
            log.info('triggering run for stage %s, flow kind %d', stage_id, flow_kind)
            stage = Stage.query.filter_by(id=stage_id).one_or_none()
            if stage is None:
                log.error('got unknown stage: %s', stage_id)
                return

            # if this stage does not have parent then start new flow
            if stage.schema['parent'] == 'root':
                flow = Flow(branch=stage.branch, kind=flow_kind)

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
            if repo_data and reason and reason['reason'] == 'repo_interval':
                reason = dict(reason='commit to repo')

            # commit new flow if created and repo changes if detected
            db.session.commit()

            # create run for current stage
            if reason is None:
                reason = dict(reason='unknown')
            execution.start_run(stage, flow, reason=reason, repo_data=repo_data)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def trigger_flow(self, project_id, trigger_data=None):
    try:
        app = _create_app()

        with app.app_context():
            log.info('triggering flow for project %s', project_id)
            project = Project.query.filter_by(id=project_id).one_or_none()
            if project is None:
                log.error('got unknown project: %s', project_id)
                return

            if trigger_data['trigger'] == 'github-push':
                branch_name = trigger_data['ref'].split('/')[-1]
                flow_kind = 'ci'
                flow_kind_no = 0
                reason = dict(reason='github push')
            elif trigger_data['trigger'] == 'github-pull_request':
                branch_name = trigger_data['pull_request']['base']['ref']
                flow_kind = 'dev'
                flow_kind_no = 1
                reason = dict(reason='github pull request')
            else:
                reason = dict(reason=trigger_data['trigger'])
            branch = Branch.query.filter_by(project=project, branch_name=branch_name).one_or_none()
            if branch is None:
                log.error('cannot find branch by branch_name: %s', branch_name)
                return

            q = Flow.query
            q = q.filter_by(branch=branch)
            q = q.filter_by(kind=flow_kind_no)
            q = q.order_by(desc(Flow.created))
            last_flow = q.first()

            # handle the case when this is the first flow in the branch
            if last_flow is None:
                execution.create_flow(branch.id, flow_kind, {})
                return

            trigger_git_url = giturlparse.parse(trigger_data['repo'])
            trigger_git_url = trigger_git_url.url2https

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
                            git_url = giturlparse.parse(git_url)
                            git_url = git_url.url2https
                            if git_url == trigger_git_url:
                                matching_stages.append(stage)
                                found = True
                                break
                    if found:
                        break

            # map runs to stages
            run_stages = {run.stage_id: run for run in last_flow.runs if not run.deleted}
            name_stages = {stage.name: stage for stage in branch.stages if not stage.deleted}

            # for stages that were not run while their parent was run, do run them
            started_something = False
            for stage in matching_stages:
                if stage.id in run_stages:
                    # TODO: trigger new flow?
                    continue
                if not stage.enabled:
                    log.info('stage %s not started - disabled', stage.id)
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

                execution.start_run(stage, last_flow, reason=reason)
                started_something = True

            if not started_something:
                execution.create_flow(branch.id, flow_kind, {}, trigger_data)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def refresh_schema_repo(self, stage_id):
    try:
        app = _create_app()

        with app.app_context():
            stage = Stage.query.filter_by(id=stage_id).one_or_none()
            if stage is None:
                log.error('got unknown stage: %s', stage_id)
                return

            planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
            planner = xmlrpc.client.ServerProxy(planner_url, allow_none=True)

            # cancel any previous scheduled refresh job
            if stage.repo_refresh_job_id:
                planner.remove_job(stage.repo_refresh_job_id)
                stage.repo_refresh_job_id = 0
                db.session.commit()

            try:
                # get schema from repo
                schema_code, version = get_schema_from_repo(stage.repo_url, stage.repo_branch, stage.repo_access_token, stage.schema_file)

                # check schema
                schema_code, schema = check_and_correct_stage_schema(stage.branch, stage.name, schema_code)
            except Exception as e:
                stage.repo_error = str(e)
                stage.repo_state = consts.REPO_STATE_ERROR
                db.session.commit()
                log.exception('problem with schema')
                return

            # store schema id db
            stage.schema = schema
            flag_modified(stage, 'schema')
            stage.schema_code = schema_code
            stage.repo_state = consts.REPO_STATE_OK
            stage.repo_error = ''
            stage.repo_version = version
            stage.schema_from_repo_enabled = True
            if stage.triggers is None:
                stage.triggers = {}
            prepare_new_planner_triggers(stage.id, schema['triggers'], stage.schema['triggers'], stage.triggers)
            flag_modified(stage, 'triggers')
            log.info('new schema: %s', stage.schema)

            # start schema refresh job
            try:
                interval = int(stage.repo_refresh_interval)
            except:
                interval = int(pytimeparse.parse(stage.repo_refresh_interval))
            job = planner.add_job('kraken.server.pljobs:refresh_schema_repo', 'interval', (stage_id,), None,
                                  None, None, None, None, None, None, False, dict(seconds=interval))

            stage.repo_refresh_job_id = job['id']
            db.session.commit()

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)
