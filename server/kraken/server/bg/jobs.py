import os
import sys
import datetime
import logging

from celery import Task
from flask import Flask
from sqlalchemy.sql.expression import asc, desc
import giturlparse

from .clry import app
from ..models import db, Executor, Run, Job, TestCaseResult, Branch, Flow, Stage
from .. import execution
from .. import consts

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


class BaseTask(Task):
    def on_success(self, retval, task_id, args, kwargs):
        #  Notify user with email
        log.info('ALL OK %s', self.name)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        #  Log unsuccessful login
        log.info('PROBLEMS')


def analyze_job_history(job):
    for job_tcr in job.results:
        log.info('Analyze %s %s', job_tcr, job_tcr.test_case.name)
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
            else:
                job_tcr.instability += 1
                job_tcr.age = 0
                if job_tcr.result == consts.TC_RESULT_PASSED and tcrs[-1].result != consts.TC_RESULT_PASSED:
                    job_tcr.change = consts.TC_RESULT_CHANGE_FIX
                elif job_tcr.result != consts.TC_RESULT_PASSED and tcrs[-1].result == consts.TC_RESULT_PASSED:
                    job_tcr.change = consts.TC_RESULT_CHANGE_REGR

        db.session.commit()


@app.task(base=BaseTask, bind=True)
def analyze_results_history(self, run_id):
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting analysis of run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run to analyze: %s', run_id)
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
            elif prev_run.state != consts.RUN_STATE_COMPLETED:
                # prev run is not completed yet
                log.info('postpone anlysis of run %s as prev run %s is not completed yet', run, prev_run)
                return

            # analyze jobs of this run
            for job in run.jobs:
                if job.covered:
                    continue
                analyze_job_history(job)
            log.info('anlysis of run %s completed', run)

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


@app.task(base=BaseTask, bind=True)
def trigger_stages(self, run_id):
    """Trigger the following stages after just completed run_id stage."""
    try:
        app = _create_app()

        with app.app_context():
            log.info('starting triggering stages after run %s', run_id)
            run = Run.query.filter_by(id=run_id).one_or_none()
            if run is None:
                log.error('got unknown run: %s', run_id)
                return

            curr_stage_name = run.stage.name
            branch = run.stage.branch
            for stage in branch.stages.filter_by(deleted=None):
                if stage.schema['parent'] != curr_stage_name:
                    continue
                if not stage.schema['triggers'].get('parent', False):
                    continue

                execution.start_run(stage, run.flow)

    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)


@app.task(base=BaseTask, bind=True)
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


@app.task(base=BaseTask, bind=True)
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


@app.task(base=BaseTask, bind=True)
def trigger_flow(self, project_id, trigger_data=None):
    try:
        app = _create_app()

        with app.app_context():
            log.info('triggering flow for project %s', project_id)
            project = Project.query.filter_by(id=project_id).one_or_none()
            if project is None:
                log.error('got unknown project: %s', project_id)
                return


            if not trigger_data:
                execution.create_flow(branch.id, 'ci', {})
                return

            branch_name = trigger_data['ref'].split('/')[-1]
            branch = Branch.query.filter_by(project=project, branch_name=branch_name).one_or_none()
            if branch is None:
                log.error('cannot find branch by branch_name: %s', branch_name)
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
                if stage_id in run_stages:
                    # TODO: trigger new flow
                    continue
                parent_name = stage.schema['parent']
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
