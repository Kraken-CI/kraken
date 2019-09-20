import logging
import datetime

from flask import make_response, abort

import consts
from models import db, Run, Stage, Job, Step, ExecutorGroup, Tool


log = logging.getLogger(__name__)


def _trigger_jobs(run):
    schema = run.stage.schema

    if 'jobs' not in schema:
        return

    started_any = False
    now = datetime.datetime.now()
    for j in schema['jobs']:
        if j['trigger'] == "on_new_run":
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


def create_run(run):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    stage_id = run.get("stage")
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    log.info("run input: %s", run)

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
