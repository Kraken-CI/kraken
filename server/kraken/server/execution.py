# Copyright 2020-2023 The Kraken Authors
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

import time
import json
import logging
from urllib.parse import urljoin

from flask import abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload

from . import consts
from . import kkrq
from . import utils
from .models import db, Project, Branch, Flow, Run, Stage, Job, Step
from .models import Issue, Artifact
from .schema import SchemaError
from . import exec_utils
from . import access
from . import chops

log = logging.getLogger(__name__)


def create_flow(branch_id, kind, body, token_info=None):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch %s not found" % branch_id)
    access.check(token_info, branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power user roles can create a flow')

    log.set_ctx(branch=branch.id)

    try:
        flow = exec_utils.create_a_flow(branch, kind, body)
    except SchemaError as e:
        abort(400, str(e))

    data = flow.get_json()

    return data, 201


def get_flows(branch_id, kind, start=0, limit=10, middle=None, token_info=None):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch %s not found" % branch_id)
    access.check(token_info, branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get flows')

    t0 = time.time()

    flows = []
    if kind == 'dev':
        kind = 1
    else:
        kind = 0
    q = Flow.query.filter_by(branch_id=branch_id, kind=kind)
    q = q.options(joinedload('branch'),
                  # joinedload('branch.project'),
                  joinedload('branch.stages'),
                  joinedload('artifacts_files'),
                  joinedload('runs'))
                  # joinedload('runs.artifacts_files'))
    if middle is None:
        total = q.count()
        q = q.order_by(desc(Flow.created))
        q = q.offset(start).limit(limit)
        for flow in q.all():
            flows.append(flow.get_json(with_project=False, with_branch=False, with_schema=False))

    else:
        q1 = q.filter(Flow.id >= middle)
        q1 = q1.order_by(asc(Flow.created))
        q1 = q1.offset(0).limit(limit)
        for flow in reversed(q1.all()):
            flows.append(flow.get_json(with_project=False, with_branch=False, with_schema=False))

        q2 = q.filter(Flow.id < middle)
        q2 = q2.order_by(desc(Flow.created))
        q2 = q2.offset(0).limit(limit)
        for flow in q2.all():
            flows.append(flow.get_json(with_project=False, with_branch=False, with_schema=False))

        total = 0

    log.info('get_flows time %s', time.time() - t0)

    return {'items': flows, 'total': total}, 200


def get_flow(flow_id, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")
    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get a flow')

    return flow.get_json()


def get_flow_runs(flow_id, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")
    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get flow runs')

    runs = []
    for run in flow.runs:
        runs.append(run.get_json())
    return runs, 200


def get_flow_artifacts(flow_id, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")
    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get flow artifacts')

    base_url = '/bk/artifacts/public/f/%d/' % flow_id

    artifacts = []
    for art in Artifact.query.filter_by(flow=flow, section=consts.ARTIFACTS_SECTION_PUBLIC):
        art = art.get_json()
        art['url'] = urljoin(base_url, art['path'].strip('/'))
        artifacts.append(art)
    return {'items': artifacts, 'total': len(artifacts)}, 200


def create_run(flow_id, body, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")
    access.check(token_info, flow.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can create a run')

    stage = Stage.query.filter_by(id=body['stage_id']).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    log.set_ctx(branch=flow.branch_id, flow_kind=flow.kind, flow=flow_id)

    run = exec_utils.start_run(stage, flow, reason=dict(reason='manual'), args=body.get('args', {}))

    # Serialize and return the newly created run in the response
    data = run.get_json()
    return data, 201


def run_run_jobs(run_id, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can run jobs')

    log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

    if run.state == consts.RUN_STATE_MANUAL:
        replay = False
    else:
        replay = True

    try:
        exec_utils.trigger_jobs(run, replay=replay)
    except SchemaError as e:
        abort(400, str(e))

    data = run.get_json()

    return data, 200


def force_run_analysis(run_id, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can run jobs')

    log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

    log.info('force analysis of run %s', run)

    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    kkrq.enq_neck(bg_jobs.analyze_run, run.id)

    data = run.get_json()

    return data, 200


def job_rerun(job_id, token_info=None):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")
    access.check(token_info, job.run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can rerun a job')

    log.set_ctx(branch=job.run.flow.branch_id, flow_kind=job.run.flow.kind, flow=job.run.flow_id, run=job.run.id)

    # TODO rerun
    job2 = Job(run=job.run, name=job.name, agents_group=job.agents_group, system=job.system, timeout=job.timeout)

    for s in job.steps:
        Step(job=job2, index=s.index, tool=s.tool, fields=s.fields)

    job.covered = True
    job2.run.state = consts.RUN_STATE_IN_PROGRESS  # need to be set in case of replay
    db.session.commit()

    data = job2.get_json()
    return data, 200


def create_job(job, token_info=None):
    run_id = job.get("run")
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can create a job')

    # TODO
    # schema = JobSchema()
    # new_job = schema.load(job, session=db.session).data
    # db.session.commit()

    # # Serialize and return the newly created person in the response
    # data = schema.dump(new_job).data
    data = {}

    return data, 201


def get_runs(stage_id, token_info=None):
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        abort(404, "Stage not found")
    access.check(token_info, stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get runs')

    q = Run.query.filter_by(stage_id=stage_id)
    runs = []
    for run in q.all():
        runs.append(run.get_json())
    return runs, 200


def get_run_jobs(run_id, start=0, limit=10, include_covered=False, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get run jobs')

    q = Job.query
    q = q.filter_by(run_id=run_id)
    if not include_covered:
        q = q.filter_by(covered=False)
    total = q.count()
    q = q.order_by(asc('id'))
    q = q.offset(start).limit(limit)
    jobs = []
    for j in q.all():
        js = j.get_json(mask_secrets=True)
        jobs.append(js)
    return {'items': jobs, 'total': total}, 200


def get_run_issues(run_id, start=0, limit=10, issue_types=None, location=None, message=None,
                   symbol=None, min_age=None, max_age=None, job=None, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get run issues')

    q = Issue.query
    q = q.options(joinedload('job'),
                  joinedload('job.agents_group'),
                  joinedload('job.agent_used'))
    q = q.join('job')
    q = q.filter(Job.run_id == run_id, Job.covered.is_(False))
    if issue_types:
        q = q.filter(Issue.issue_type.in_(issue_types))
    if location is not None:
        q = q.filter(Issue.path.ilike('%' + location + '%'))
    if message is not None:
        q = q.filter(Issue.message.ilike('%' + message + '%'))
    if symbol is not None:
        q = q.filter(Issue.symbol.ilike('%' + symbol + '%'))
    if min_age is not None:
        q = q.filter(Issue.age >= min_age)
    if max_age is not None:
        q = q.filter(Issue.age <= max_age)
    if job is not None:
        if job.isdigit():
            job_id = int(job)
            q = q.filter(Job.id == job_id)
        else:
            q = q.filter(Job.name.ilike('%' + job + '%'))

    total = q.count()
    q = q.order_by(asc('path'), asc('line'))
    q = q.offset(start).limit(limit)
    issues = []
    for i in q.all():
        issues.append(i.get_json())
    return {'items': issues, 'total': total}, 200


def get_run_artifacts(run_id, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get run artifacts')

    base_url = '/bk/artifacts/public/r/%d/' % run.id

    artifacts = []
    for art in Artifact.query.filter_by(run=run, section=consts.ARTIFACTS_SECTION_PUBLIC):
        art = art.get_json()
        art['url'] = urljoin(base_url, art['path'].strip('/'))
        artifacts.append(art)
    return {'items': artifacts, 'total': len(artifacts)}, 200


def get_run(run_id, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get a run')

    return run.get_json(), 200


def get_job_logs(job_id, start=0, limit=200, order=None, internals=False, filters=None, token_info=None):  # pylint: disable=unused-argument
    if order not in [None, 'asc', 'desc']:
        abort(400, "incorrect order value: %s" % str(order))

    if start < 0:
        abort(400, "incorrect start value: %s" % str(start))

    if limit < 0:
        abort(400, "incorrect limit value: %s" % str(limit))

    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")
    access.check(token_info, job.run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get job logs')

    job_json = job.get_json()

    ch = chops.get_clickhouse()

    internal_clause = ''
    if not internals:
        internal_clause = "and tool != '' and service = 'agent'"

    query = "select count(*) from logs where job = %%(job_id)d %s" % internal_clause
    params = dict(job_id=job_id)
    resp = ch.execute(query, params)
    total = resp[0][0]

    if order is None:
        order = 'asc'

    query = "select time,message,service,host,level,job,tool,step from logs where job = %%(job_id)d %s order by time %s, seq %s limit %%(start)d, %%(limit)d"
    query %= (internal_clause, order, order)
    params = dict(job_id=job_id, start=start, limit=limit)

    rows = ch.execute(query, params)

    logs = []
    for r in rows:
        entry = dict(time=r[0],
                     message=r[1],
                     service=r[2],
                     host=r[3],
                     level=r[4].lower()[:4],
                     job=r[5],
                     tool=r[6],
                     step=r[7])
        logs.append(entry)

    return {'items': logs, 'total': total, 'job': job_json}, 200


def get_job(job_id, token_info=None):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")
    access.check(token_info, job.run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get a job')

    return job.get_json()


def get_step_logs(job_id, step_idx, start=0, limit=200, order=None, filters=None, token_info=None):  # pylint: disable=unused-argument
    if order not in [None, 'asc', 'desc']:
        abort(400, "incorrect order value: %s" % str(order))

    if start < 0:
        abort(400, "incorrect start value: %s" % str(start))

    if limit < 0:
        abort(400, "incorrect limit value: %s" % str(limit))

    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")
    access.check(token_info, job.run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get job logs')

    job_json = job.get_json()

    ch = chops.get_clickhouse()

    query = "SELECT count(*) FROM logs WHERE job = %(job_id)d AND step = %(step_idx)d"
    params = dict(job_id=job_id, step_idx=step_idx)
    resp = ch.execute(query, params)
    total = resp[0][0]

    if order is None:
        order = 'asc'

    query = "SELECT time,message,service,host,level,job,tool,step "
    query += " FROM logs WHERE job = %%(job_id)d AND step = %%(step_idx)d "
    query += " ORDER BY time %s, seq %s LIMIT %%(start)d, %%(limit)d"
    query %= (order, order)
    params = dict(job_id=job_id, step_idx=step_idx, start=start, limit=limit)

    rows = ch.execute(query, params)

    logs = []
    for r in rows:
        entry = dict(time=r[0],
                     message=r[1],
                     service=r[2],
                     host=r[3],
                     level=r[4].lower()[:4],
                     job=r[5],
                     tool=r[6],
                     step=r[7])
        logs.append(entry)

    return {'items': logs, 'total': total, 'job': job_json}, 200


def get_logs(branch_id=None, flow_kind=None, flow_id=None, run_id=None, job_id=None, step_idx=None,
             agent_id=None, services=None, level=None,
             start=0, limit=200, order=None, token_info=None):  # pylint: disable=unused-argument
    if start < 0:
        abort(400, "incorrect start value: %s" % str(start))

    if limit < 0:
        abort(400, "incorrect limit value: %s" % str(limit))

    if order not in [None, 'asc', 'desc']:
        abort(400, "incorrect order value: %s" % str(order))

    if order is None:
        order = 'asc'

    _, where_clause, params = chops.prepare_logs_query(
        branch_id, flow_kind, flow_id, run_id, job_id, step_idx,
        agent_id, services, level, token_info)

    params['start'] = start
    params['limit'] = limit

    ch = chops.get_clickhouse()

    # get total first
    total_query = "SELECT count(*) FROM logs %s" % where_clause
    resp = ch.execute(total_query, params)
    total = resp[0][0]

    # get logs now
    query = "SELECT time,message,service,host,path,lineno,level,branch,flow_kind,flow,run,job,tool,step,agent "
    query += f" FROM logs {where_clause} ORDER BY time {order}, seq {order} LIMIT %(start)d, %(limit)d"
    log.info('CH query %s', query)
    log.info('CH params %s', params)
    rows = ch.execute(query, params)

    logs = []
    for r in rows:
        entry = dict(time=r[0],
                     message=r[1],
                     service=r[2],
                     host=r[3],
                     path=r[4],
                     lineno=r[5],
                     level=r[6].lower()[:4],
                     branch=r[7],
                     flow_kind=r[8],
                     flow=r[9],
                     run=r[10],
                     job=r[11],
                     tool=r[12],
                     step=r[13],
                     agent=r[14])
        logs.append(entry)

    return {'items': logs, 'total': total}, 200


def cancel_run(run_id, token_info=None):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    access.check(token_info, run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can cancel a run')

    # if run is completed then do nothing
    if run.state == consts.RUN_STATE_COMPLETED:
        return {}

    log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

    # cancel any pending job
    all_completed = True
    for job in run.jobs:
        if job.state != consts.JOB_STATE_COMPLETED:
            log.set_ctx(job=job.id)
            exec_utils.cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)
            all_completed = False
        log.set_ctx(job=None)

    # if all jobs already completed or there is no jobs then complete run
    if all_completed:
        now = utils.utcnow()
        exec_utils.complete_run(run, now)

    run.note = 'run %d canceled by user' % run.id
    db.session.commit()

    return {}


def delete_job(job_id, token_info=None):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")
    access.check(token_info, job.run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power roles can cancel a job')

    log.set_ctx(branch=job.run.flow.branch_id, flow_kind=job.run.flow.kind, flow=job.run.flow_id, run=job.run.id, job=job.id)

    exec_utils.cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)

    return {}


def get_agent_jobs(agent_id, start=0, limit=10, token_info=None):
    access.check(token_info, '', 'admin',
                 'only superadmin role can get agent jobs')
    q = Job.query
    q = q.filter_by(agent_used_id=agent_id)
    total = q.count()
    q = q.order_by(desc('id'))
    q = q.offset(start).limit(limit)
    jobs = []
    for j in q.all():
        jobs.append(j.get_json())
    return {'items': jobs, 'total': total}, 200


def get_user_data(scope, entity_id, token_info=None):
    if scope == 'flow':
        flow = Flow.query.filter_by(id=entity_id).one_or_none()
        data = flow.user_data
        project_id = flow.branch.project_id
    elif scope.startswith('branch'):
        branch = Branch.query.filter_by(id=entity_id).one_or_none()
        if scope == 'branch-ci':
            data = branch.user_data_ci
        elif scope == 'branch-dev':
            data = branch.user_data_dev
        elif scope == 'branch':
            data = branch.user_data
        project_id = branch.project_id
    elif scope == 'project':
        project = Project.query.filter_by(id=entity_id).one_or_none()
        data = project.user_data
        project_id = project.id

    access.check(token_info, project_id, 'view',
                 'only superadmin, project admin, project power and project viewer user roles can get branch logs')

    resp = dict(data=json.dumps(data, indent=4))

    return resp, 200
