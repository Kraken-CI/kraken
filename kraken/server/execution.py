import logging
import datetime

from flask import make_response, abort
from sqlalchemy.sql.expression import asc, desc

import consts
from models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult
from models import Project

log = logging.getLogger(__name__)


def _trigger_jobs(run):
    schema = run.stage.schema

    if 'jobs' not in schema:
        return

    started_any = False
    now = datetime.datetime.utcnow()
    for j in schema['jobs']:
        # check tools in steps
        tools = []
        tool_not_found = None
        for idx, s in enumerate(j['steps']):
            tool = Tool.query.filter_by(name=s['tool']).one_or_none()
            if tool is None:
                tool_not_found = s['tool']
                break
            tools.append(tool)
        if tool_not_found is not None:
            log.warn('cannot find tool %s', tool_not_found)

        envs = j['environments']
        for env in envs:
            executor_group = ExecutorGroup.query.filter_by(project=run.stage.branch.project, name=env['executor_group']).one_or_none()
            if executor_group is None:
                log.warn("cannot find executor group '%s'", env['executor_group'])
                continue
            job = Job(run=run, name=j['name'], executor_group=executor_group)
            if tool_not_found:
                job.state = consts.JOB_STATE_COMPLETED
                job.completion_status = consts.JOB_CMPLT_MISSING_TOOL_IN_DB
                job.notes = "cannot find tool '%s' in database" % s['tool']
            else:
                for idx, s in enumerate(j['steps']):
                    fields = s.copy()
                    del fields['tool']
                    Step(job=job, index=idx, tool=tools[idx], fields=fields)
            db.session.commit()
            log.info('created job %s', job.get_json())
            started_any = True

    if started_any:
        run.started = now
        db.session.commit()


def create_flow(branch_id):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    flow = Flow(branch=branch)
    db.session.commit()

    for stage in branch.stages:
        if stage.schema['trigger'] != 'initial':
            continue

        run = Run(flow=flow, stage=stage)
        db.session.commit()

        _trigger_jobs(run)

    data = flow.get_json()

    return data, 201


def get_flows(branch_id):
    q = Flow.query.filter_by(branch_id=branch_id).order_by(desc(Flow.created))
    flows = []
    for flow in q.all():
        flows.append(flow.get_json())
    return flows, 200


def create_run(stage_id):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    new_run = Run(stage=stage)
    db.session.commit()

    _trigger_jobs(new_run)

    # Serialize and return the newly created run in the response
    data = new_run.get_json()

    return data, 201


def create_job(job):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    run_id = job.get("run")
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    log.info("job input: %s", job)

    # Create a person instance using the schema and the passed in person
    schema = JobSchema()
    new_job = schema.load(job, session=db.session).data
    db.session.commit()

    # Serialize and return the newly created person in the response
    data = schema.dump(new_job).data

    return data, 201


def get_runs(stage_id):
    q = Run.query.filter_by(stage_id=stage_id)
    runs = []
    for run in q.all():
        runs.append(run.get_json())
    return runs, 200


def get_run_results(run_id):
    q = TestCaseResult.query.join('job').filter(Job.run_id == run_id)
    results = []
    for r in q.all():
        results.append(r.get_json())
    return {'items': results, 'total': len(results)}, 200


def get_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run:
        return run.get_json(), 200
    return {}, 404


def get_projects():
    q = Project.query
    projects = []
    for p in q.all():
        projects.append(p.get_json())
    return {'items': projects, 'total': len(projects)}, 200


def get_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch:
        return branch.get_json(), 200
    return {}, 404
