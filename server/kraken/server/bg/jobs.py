import os
import datetime
import logging

from celery import Task
from flask import Flask
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified
import giturlparse

from .clry import app as clry_app
from ..models import db, Run, Job, TestCaseResult, Branch, Flow, Stage, Project, Issue
from .. import execution  # pylint: disable=cyclic-import
from .. import consts
from .. import notify

log = logging.getLogger(__name__)


def _create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)

    #logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

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


def _analyze_job_results_history(job):
    # TODO: if branch is forked from another base branch take base branch results into account

    # simple stats
    tests_total = 0
    tests_passed = 0
    tests_not_run = 0

    # history stats
    new_cnt = 0
    no_change_cnt = 0
    regr_cnt = 0
    fix_cnt = 0

    for job_tcr in job.results:
        # simple results stats
        tests_total += 1
        if job_tcr.result == consts.TC_RESULT_PASSED:
            tests_passed += 1
        elif job_tcr.result == consts.TC_RESULT_NOT_RUN:
            tests_not_run += 1

        # analyze history, get previous 10 results for each TCR
        log.info('Analyze result %s %s', job_tcr, job_tcr.test_case.name)
        q = TestCaseResult.query
        q = q.filter(TestCaseResult.id != job_tcr.id)
        q = q.filter_by(test_case_id=job_tcr.test_case_id)
        q = q.join('job')
        q = q.filter_by(executor_group=job_tcr.job.executor_group)
        q = q.join('job', 'run', 'flow', 'branch')
        q = q.filter(Branch.id == job.run.flow.branch_id)
        q = q.order_by(asc(Flow.created))
        q = q.limit(10)

        tcrs = q.all()
        # determine instability
        for idx, tcr in enumerate(tcrs):
            if idx == 0:
                job_tcr.instability = 0
            elif tcr.result != tcrs[idx - 1].result:
                job_tcr.instability += 1

            log.info('TCR: %s %s %s', tcr, tcr.test_case.name, tcr.job.run.flow.created)

        # determine age
        if len(tcrs) > 0:
            if tcrs[-1].result == job_tcr.result:
                job_tcr.age = tcrs[-1].age + 1
                no_change_cnt += 1
            else:
                job_tcr.instability += 1
                job_tcr.age = 0
                if job_tcr.result == consts.TC_RESULT_PASSED and tcrs[-1].result != consts.TC_RESULT_PASSED:
                    job_tcr.change = consts.TC_RESULT_CHANGE_FIX
                    fix_cnt += 1
                elif job_tcr.result != consts.TC_RESULT_PASSED and tcrs[-1].result == consts.TC_RESULT_PASSED:
                    job_tcr.change = consts.TC_RESULT_CHANGE_REGR
                    regr_cnt += 1
        else:
            job_tcr.change = consts.TC_RESULT_CHANGE_NEW
            new_cnt += 1

        db.session.commit()

    return tests_total, tests_passed, tests_not_run, new_cnt, no_change_cnt, regr_cnt, fix_cnt


def _analyze_job_issues_history(job):
    q = Run.query.filter_by(stage=job.run.stage)
    q = q.filter(Run.created < job.run.created)
    q = q.order_by(desc(Run.created))
    prev_run = q.first()
    if prev_run is None:
        return 0, 0

    issues_total = 0
    issues_new = 0

    for issue in job.issues:
        issues_total += 1

        log.info('Analyze issue %s', issue)
        q = Issue.query
        q = q.filter_by(path=issue.path, issue_type=issue.issue_type, symbol=issue.symbol)
        q = q.filter(Issue.line > issue.line - 5, Issue.line < issue.line + 5)
        q = q.join('job')
        q = q.filter_by(executor_group=issue.job.executor_group)
        q = q.join('job', 'run')
        q = q.filter(Run.id == prev_run.id)
        prev_issues = q.all()
        prev_issue = None
        dist = 1000
        log.info('PREV ISSES %s', len(prev_issues))
        for i in prev_issues:
            new_dist = abs(i.line - issue.line)
            log.info('issue %s - prev issue %s, dist %s', issue, i, new_dist)
            if new_dist < dist:
                dist = new_dist
                prev_issue = i

        if prev_issue is not None:
            issue.age = prev_issue.age + 1
        if issue.age == 0:
            issues_new += 1
    db.session.commit()

    return issues_total, issues_new


@clry_app.task(base=BaseTask, bind=True)
def analyze_results_history(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting results history analysis of run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to analyze results history: %s', run_id)
                return

            # check prev run
            q = Run.query
            q = q.filter_by(stage_id=run.stage_id)
            q = q.join('flow')
            q = q.filter(Flow.created < run.flow.created)
            q = q.order_by(desc(Flow.created))
            prev_run = q.first()
            if prev_run is None:
                log.info('skip anlysis of run %s as there is no prev run', run)
                return
            if prev_run.state != consts.RUN_STATE_COMPLETED:
                # prev run is not completed yet
                log.info('postpone anlysis of run %s as prev run %s is not completed yet', run, prev_run)
                return

            # analyze jobs of this run
            run.new_cnt = run.no_change_cnt = run.regr_cnt = run.fix_cnt = 0
            run.tests_total = run.tests_passed = run.tests_not_run = 0
            run.jobs_error = run.jobs_total = 0
            run.issues_total = run.issues_new = 0
            non_covered_jobs = Job.query.filter_by(run=run).filter_by(covered=False).all()
            for job in non_covered_jobs:
                # analyze results history
                counts = _analyze_job_results_history(job)
                tests_total, tests_passed, tests_not_run, new_cnt, no_change_cnt, regr_cnt, fix_cnt = counts
                run.new_cnt += new_cnt
                run.no_change_cnt += no_change_cnt
                run.regr_cnt += regr_cnt
                run.fix_cnt += fix_cnt
                run.tests_total += tests_total
                run.tests_passed += tests_passed
                run.tests_not_run += tests_not_run
                db.session.commit()

                # analyze issues history
                issues_total, issues_new = _analyze_job_issues_history(job)
                run.issues_total += issues_total
                run.issues_new += issues_new
                db.session.commit()

                # compute jobs stats
                run.jobs_total += 1
                if job.completion_status not in [consts.JOB_CMPLT_ALL_OK, None]:
                    run.jobs_error += 1
                db.session.commit()

            log.info('anlysis of run %s completed', run)

            t = notify_about_completed_run.delay(run.id)
            log.info('enqueued notification about completion of run %s, bg processing: %s', run, t)

            # trigger analysis of the following run
            q = Run.query
            q = q.filter_by(stage_id=run.stage_id)
            q = q.join('flow')
            q = q.filter(Flow.created > run.flow.created)
            q = q.order_by(asc(Flow.created))
            next_run = q.first()
            if next_run is not None:
                t = analyze_results_history.delay(next_run.id)
                log.info('enqueued anlysis of run %s, bg processing: %s', next_run, t)

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

            notify.notify(run)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def trigger_stages(self, run_id):
    """Trigger the following stages after just completed run_id stage."""
    try:
        app = _create_app()

        with app.app_context():
            # find completed parent run
            log.info('starting triggering stages after run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run: %s', run_id)
                return

            # go through next stages and trigger them if needed
            curr_stage_name = run.stage.name
            branch = run.stage.branch
            for stage in branch.stages.filter_by(deleted=None, enabled=True):
                if stage.schema['parent'] != curr_stage_name:
                    continue
                if not stage.schema['triggers'].get('parent', False):
                    continue

                if stage.enabled:
                    execution.start_run(stage, run.flow)
                else:
                    log.info('stage %s not started because it is disabled', stage.name)

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
    q = q.filter_by(completion_status=consts.JOB_CMPLT_ALL_OK)
    q = q.filter_by(covered=False)
    q = q.filter_by(executor_group=job.executor_group)
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

    max_duration = duration = job.finished - job.assigned
    prev_job_id = job.id
    for j in jobs:
        if not job.assigned or not job.finished:
            log.warning('job %s has None dates: %s %s', job, job.assigned, job.finished)
            continue
        if job.assigned > job.finished:
            log.warning('job %s has wrong dates: %s %s', job, job.assigned, job.finished)
            continue

        if j.id == prev_job_id:
            duration += j.finished - j.assigned
        else:
            duration = j.finished - j.assigned
            prev_job_id = j.id

        if duration > max_duration:
            max_duration = duration

    timeout = int(max_duration.total_seconds() * 1.7)
    if timeout < 60:
        timeout = 60
    stage = job.run.stage
    log.info("new timeout for job '%s' in stage '%s': %ssecs", job.name, stage.name, timeout)
    if stage.timeouts is None:
        stage.timeouts = {}
    stage.timeouts[job.name] = timeout
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

            if job.state != consts.JOB_STATE_COMPLETED:
                job.completed = now
                job.state = consts.JOB_STATE_COMPLETED
                job.completion_status = consts.JOB_CMPLT_ALL_OK
                log.info('checking steps')
                for step in job.steps:
                    log.info('%s: %s', step.index, consts.STEP_STATUS_NAME[step.status] if step.status in consts.STEP_STATUS_NAME else step.status)
                    if step.status == consts.STEP_STATUS_ERROR:
                        job.completion_status = consts.JOB_CMPLT_AGENT_ERROR_RETURNED
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
        raise self.retry(exc=exc)


@clry_app.task(base=BaseTask, bind=True)
def trigger_run(self, stage_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('triggering run for stage %s', stage_id)
            stage = Stage.query.filter_by(id=stage_id).one_or_none()
            if stage is None:
                log.error('got unknown stage: %s', stage_id)
                return

            # if this stage does not have parent then start new flow
            if stage.schema['parent'] == 'root':
                flow = Flow(branch=stage.branch)
                db.session.commit()

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

            # create run for current stage
            execution.start_run(stage, flow)

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

            branch_name = trigger_data['ref'].split('/')[-1]
            branch = Branch.query.filter_by(project=project, branch_name=branch_name).one_or_none()
            if branch is None:
                log.error('cannot find branch by branch_name: %s', branch_name)
                return

            if not trigger_data:
                execution.create_flow(branch.id, 'ci', {})
                return

            q = Flow.query
            q = q.filter_by(branch=branch)
            q = q.order_by(desc(Flow.created))
            last_flow = q.first()

            if last_flow is None:
                execution.create_flow(branch.id, 'ci', {})
                return

            trigger_git_url = giturlparse.parse(trigger_data['repo'])
            trigger_git_url = trigger_git_url.url2https

            # find stages that use repo from trigger
            matching_stages = []
            for stage in branch.stages.filter_by(deleted=None):
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
            name_stages = {stage.name: stage for stage in branch.stages}

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

                execution.start_run(stage, last_flow)
                started_something = True

            if not started_something:
                execution.create_flow(branch.id, 'ci', {}, trigger_data)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)
