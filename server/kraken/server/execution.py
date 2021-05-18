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
from urllib.parse import urljoin, urlparse

from flask import abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
import clickhouse_driver

from . import consts
from .models import db, Branch, Flow, Run, Stage, Job, Step, TestCaseResult
from .models import TestCase, Issue, Artifact
from .schema import SchemaError
from . import exec_utils

log = logging.getLogger(__name__)


def create_flow(branch_id, kind, body):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    try:
        flow = exec_utils.create_a_flow(branch, kind, body)
    except SchemaError as e:
        abort(400, str(e))

    data = flow.get_json()

    return data, 201


def get_flows(branch_id, kind, start=0, limit=10, middle=None):
    flows = []
    if kind == 'dev':
        kind = 1
    else:
        kind = 0
    q = Flow.query.filter_by(branch_id=branch_id, kind=kind)
    q = q.options(joinedload('branch'),
                  joinedload('branch.project'),
                  joinedload('branch.stages'),
                  joinedload('artifacts_files'),
                  joinedload('runs'),
                  joinedload('runs.artifacts_files'))
    if middle is None:
        total = q.count()
        q = q.order_by(desc(Flow.created))
        q = q.offset(start).limit(limit)
        for flow in q.all():
            flows.append(flow.get_json())
    else:
        q1 = q.filter(Flow.id >= middle)
        q1 = q1.order_by(asc(Flow.created))
        q1 = q1.offset(0).limit(limit)
        for flow in reversed(q1.all()):
            flows.append(flow.get_json())

        q2 = q.filter(Flow.id < middle)
        q2 = q2.order_by(desc(Flow.created))
        q2 = q2.offset(0).limit(limit)
        for flow in q2.all():
            flows.append(flow.get_json())

        total = 0

    return {'items': flows, 'total': total}, 200


def get_flow(flow_id):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")
    return flow.get_json()


def get_flow_runs(flow_id):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")

    runs = []
    for run in flow.runs:
        runs.append(run.get_json())
    return runs, 200


def get_flow_artifacts(flow_id):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")

    base_url = '/artifacts/public/f/%d/' % flow_id

    artifacts = []
    for art in Artifact.query.filter_by(flow=flow, section=consts.ARTIFACTS_SECTION_PUBLIC):
        art = art.get_json()
        art['url'] = urljoin(base_url, art['path'].strip('/'))
        artifacts.append(art)
    return {'items': artifacts, 'total': len(artifacts)}, 200


def create_run(flow_id, body):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")

    stage = Stage.query.filter_by(id=body['stage_id']).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    run = exec_utils.start_run(stage, flow, reason=dict(reason='manual'), args=body.get('args', {}))

    # Serialize and return the newly created run in the response
    data = run.get_json()
    return data, 201


def run_run_jobs(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

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


def job_rerun(job_id):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    # TODO rerun
    job2 = Job(run=job.run, name=job.name, agents_group=job.agents_group, system=job.system, timeout=job.timeout)

    for s in job.steps:
        Step(job=job2, index=s.index, tool=s.tool, fields=s.fields)

    job.covered = True
    job2.run.state = consts.RUN_STATE_IN_PROGRESS  # need to be set in case of replay
    db.session.commit()

    data = job2.get_json()
    return data, 200


def create_job(job):
    run_id = job.get("run")
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    log.info("job input: %s", job)

    # TODO
    # schema = JobSchema()
    # new_job = schema.load(job, session=db.session).data
    # db.session.commit()

    # # Serialize and return the newly created person in the response
    # data = schema.dump(new_job).data
    data = {}

    return data, 201


def get_runs(stage_id):
    q = Run.query.filter_by(stage_id=stage_id)
    runs = []
    for run in q.all():
        runs.append(run.get_json())
    return runs, 200


def get_run_results(run_id, start=0, limit=10, sort_field="name", sort_dir="asc",
                    statuses=None, changes=None,
                    min_age=None, max_age=None,
                    min_instability=None, max_instability=None,
                    test_case_text=None, job=None):
    log.info('filters %s %s %s %s %s %s', statuses, changes, min_age, max_age, min_instability, max_instability)
    q = TestCaseResult.query
    q = q.options(joinedload('test_case'),
                  joinedload('job'),
                  joinedload('job.agents_group'),
                  joinedload('job.agent_used'))
    q = q.join('job')
    q = q.filter(Job.run_id == run_id, Job.covered.is_(False))
    if statuses:
        q = q.filter(TestCaseResult.result.in_(statuses))
    if changes:
        q = q.filter(TestCaseResult.change.in_(changes))
    if min_age is not None:
        q = q.filter(TestCaseResult.age >= min_age)
    if max_age is not None:
        q = q.filter(TestCaseResult.age <= max_age)
    if min_instability is not None:
        q = q.filter(TestCaseResult.instability >= min_instability)
    if max_instability is not None:
        q = q.filter(TestCaseResult.instability <= max_instability)
    if test_case_text is not None:
        q = q.join('test_case').filter(TestCase.name.ilike('%' + test_case_text + '%'))
    if job is not None:
        if job.isdigit():
            job_id = int(job)
            q = q.filter(Job.id == job_id)
        else:
            q = q.filter(Job.name.ilike('%' + job + '%'))

    total = q.count()

    sort_func = asc
    if sort_dir == "desc":
        sort_func = desc

    if sort_field == "result":
        q = q.order_by(sort_func('result'))
    elif sort_field == "change":
        q = q.order_by(sort_func('change'))
    elif sort_field == "age":
        q = q.order_by(sort_func('age'))
    elif sort_field == "instability":
        q = q.order_by(sort_func('instability'))
    elif sort_field == "relevancy":
        q = q.order_by(sort_func('relevancy'))
    else:
        q = q.join('test_case').order_by(sort_func('name'))

    q = q.offset(start).limit(limit)
    results = []
    for tcr in q.all():
        results.append(tcr.get_json())
    return {'items': results, 'total': total}, 200


def get_run_jobs(run_id, start=0, limit=10, include_covered=False):
    q = Job.query
    q = q.filter_by(run_id=run_id)
    if not include_covered:
        q = q.filter_by(covered=False)
    total = q.count()
    q = q.order_by(asc('id'))
    q = q.offset(start).limit(limit)
    jobs = []
    for j in q.all():
        jobs.append(j.get_json())
    return {'items': jobs, 'total': total}, 200


def get_run_issues(run_id, start=0, limit=10, issue_types=None, location=None, message=None, symbol=None, min_age=None, max_age=None, job=None):
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


def get_run_artifacts(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    base_url = '/artifacts/public/r/%d/' % run.id

    artifacts = []
    for art in Artifact.query.filter_by(run=run, section=consts.ARTIFACTS_SECTION_PUBLIC):
        art = art.get_json()
        art['url'] = urljoin(base_url, art['path'].strip('/'))
        artifacts.append(art)
    return {'items': artifacts, 'total': len(artifacts)}, 200


def get_result_history(test_case_result_id, start=0, limit=10):
    tcr = TestCaseResult.query.filter_by(id=test_case_result_id).one_or_none()

    q = TestCaseResult.query
    q = q.options(joinedload('test_case'),
                  joinedload('job'),
                  joinedload('job.agents_group'),
                  joinedload('job.agent_used'))
    q = q.filter_by(test_case_id=tcr.test_case_id)
    q = q.join('job')
    q = q.filter_by(agents_group=tcr.job.agents_group)
    q = q.filter_by(system=tcr.job.system)
    q = q.join('job', 'run', 'flow', 'branch')
    q = q.filter(Branch.id == tcr.job.run.flow.branch_id)
    q = q.filter(Flow.kind == 0)  # CI
    q = q.filter(Flow.created <= tcr.job.run.flow.created)
    q = q.order_by(desc(Flow.created))

    total = q.count()
    q = q.offset(start).limit(limit)
    results = []
    if tcr.job.run.flow.kind == 1:  # DEV
        results.append(tcr.get_json(with_extra=True))
    for tcr in q.all():
        results.append(tcr.get_json(with_extra=True))
    return {'items': results, 'total': total}, 200


def get_result(test_case_result_id):
    tcr = TestCaseResult.query.filter_by(id=test_case_result_id).one_or_none()
    if tcr is None:
        abort(404, "Run not found")
    return tcr.get_json(with_extra=True), 200


def get_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")
    return run.get_json(), 200


def  get_job_logs(job_id, start=0, limit=200, order=None, internals=False, filters=None):  # pylint: disable=unused-argument
    if order not in [None, 'asc', 'desc']:
        abort(400, "incorrect order value: %s" % str(order))

    job = Job.query.filter_by(id=job_id).one()
    job_json = job.get_json()

    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

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


def cancel_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    for job in run.jobs:
        exec_utils.cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)

    return {}


def delete_job(job_id):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    exec_utils.cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)

    return {}
