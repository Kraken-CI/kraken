import os
import sys
import datetime
import logging

from celery import Task
from flask import Flask
from sqlalchemy.sql.expression import asc, desc

from bg.clry import app
from models import db, Executor, Run, Job, TestCaseResult, Branch, Flow
import consts

log = logging.getLogger(__name__)


def create_app():
    #logging.basicConfig(format=consts.LOG_FMT, level=logging.INFO)

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # db url
    db_url = os.environ.get('DB_URL', "postgresql://kraken:kk123@localhost:5433/kraken")

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
        app = create_app()

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
def job_completed(self, job_id):
    try:
        app = create_app()

        with app.app_context():

            now = datetime.datetime.utcnow()

            log.info('completing job %s', job_id)
            job = Job.query.filter_by(id=job_id).one_or_none()
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
            new_state = consts.RUN_STATE_COMPLETED
            for j in run.jobs:
                if j.state != consts.JOB_STATE_COMPLETED:
                    new_state = consts.RUN_STATE_IN_PROGRESS
                    break

            if run.state != new_state:
                log.info('completed run %s', run)
                run.state = new_state
                run.finished = now
                db.session.commit()

                # establish new flow state
                flow = run.flow
                new_state = consts.FLOW_STATE_COMPLETED
                for r in flow.runs:
                    if r.state != consts.RUN_STATE_COMPLETED:
                        new_state = consts.FLOW_STATE_IN_PROGRESS
                        break

                if flow.state != new_state:
                    log.info('completed flow %s', flow)
                    flow.state = new_state
                    flow.finished = now
                    db.session.commit()

                # trigger history of results analysis
                t = analyze_results_history.delay(run.id)
                log.info('run %s finished, bg processing: %s', run, t)
    except Exception as exc:
        log.exception('will retry')
        raise self.retry(exc=exc)
