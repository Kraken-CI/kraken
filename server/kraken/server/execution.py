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
import re
import logging
import datetime
from urllib.parse import urljoin

from flask import abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
from elasticsearch import Elasticsearch

from . import consts
from .models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult, TestCase, Issue, Artifact

log = logging.getLogger(__name__)


def complete_run(run, now):
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    log.info('completed run %s', run)
    run.state = consts.RUN_STATE_COMPLETED
    run.finished = now
    db.session.commit()

    # trigger any following stages to currently completed run
    t = bg_jobs.trigger_stages.delay(run.id)
    log.info('run %s completed, trigger the following stages: %s', run, t)

    # establish new state for flow
    flow = run.flow
    is_completed = True
    for r in flow.runs:
        if r.state != consts.RUN_STATE_COMPLETED:
            is_completed = False
            break

    if is_completed:
        log.info('completed flow %s', flow)
        flow.state = consts.FLOW_STATE_COMPLETED
        flow.finished = now
        db.session.commit()

    # trigger results history analysis
    t = bg_jobs.analyze_results_history.delay(run.id)
    log.info('run %s completed, analyze results history: %s', run, t)


def _substitute_vars(fields, args):
    new_fields = {}
    for f, val in fields.items():
        if not isinstance(val, str):
            new_fields[f] = val
            continue
        for var in re.findall('#{[A-Z]+}', val):
            name = var[2:-1]
            if name in args:
                arg_val = args[name]
                val = val.replace(var, arg_val)
        new_fields[f] = val
    return new_fields


def trigger_jobs(run, replay=False):
    log.info('triggering jobs for run %s', run)
    schema = run.stage.schema

    # find any prev jobs that will be covered by jobs triggered here in this function
    covered_jobs = {}
    if replay:
        q = Job.query.filter_by(run=run).filter_by(covered=False)
        for j in q.all():
            key = '%s-%s' % (j.name, j.executor_group_id)
            if key not in covered_jobs:
                covered_jobs[key] = [j]
            else:
                covered_jobs[key].append(j)

    # trigger new jobs based on jobs defined in stage schema
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
            log.warning('cannot find tool %s', tool_not_found)

        envs = j['environments']
        for env in envs:
            # get executor group
            q = ExecutorGroup.query
            q = q.filter_by(project=run.stage.branch.project, name=env['executor_group'])
            executor_group = q.one_or_none()

            if executor_group is None:
                executor_group = ExecutorGroup.query.filter_by(name=env['executor_group']).one_or_none()
                if executor_group is None:
                    log.warning("cannot find executor group '%s'", env['executor_group'])
                    continue

            # get timeout
            if run.stage.timeouts and j['name'] in run.stage.timeouts:
                # take estimated timeout if present
                timeout = run.stage.timeouts[j['name']]
            else:
                # take initial timeout from schema, or default one
                timeout = j.get('timeout', 5 * 60)  # default job timeout is 5mins
                if timeout < 60:
                    timeout = 60

            # create job
            job = Job(run=run, name=j['name'], executor_group=executor_group, system=env['system'], timeout=timeout)

            if tool_not_found:
                job.state = consts.JOB_STATE_COMPLETED
                job.completion_status = consts.JOB_CMPLT_MISSING_TOOL_IN_DB
                job.notes = "cannot find tool '%s' in database" % tool_not_found
            else:
                # substitute vars in steps
                for idx, s in enumerate(j['steps']):
                    fields = _substitute_vars(s, run.args)
                    del fields['tool']
                    Step(job=job, index=idx, tool=tools[idx], fields=fields)

            # if this is rerun/replay then mark prev jobs as covered
            if replay:
                key = '%s-%s' % (j['name'], executor_group.id)
                if key in covered_jobs:
                    for cj in covered_jobs[key]:
                        cj.covered = True
                        # TODO: we should cancel these jobs if they are still running

            db.session.commit()
            log.info('created job %s', job.get_json())
            started_any = True

    if started_any or len(schema['jobs']) == 0:
        run.started = now
        db.session.commit()

        if len(schema['jobs']) == 0:
            complete_run(run, now)


def start_run(stage, flow, args=None):
    run_args = stage.get_default_args()
    if args is not None:
        run_args.update(args)
    new_run = Run(stage=stage, flow=flow, args=run_args)
    db.session.commit()
    log.info('starting run %s for stage %s of branch %s', new_run, stage, stage.branch)
    trigger_jobs(new_run)
    return new_run


def create_flow(branch_id, kind, flow, trigger_data=None):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")

    if kind == 'dev':
        kind = 1
    else:
        kind = 0

    args = flow.get('args', {})
    flow_args = args.get('Common', {})
    branch_name = flow_args.get('BRANCH', branch.branch_name)
    if 'BRANCH' in flow_args:
        del flow_args['BRANCH']

    flow = Flow(branch=branch, kind=kind, branch_name=branch_name, args=flow_args, trigger_data=trigger_data)
    db.session.commit()

    for stage in branch.stages.filter_by(deleted=None):
        if stage.schema['parent'] != 'root' or stage.schema['triggers'].get('parent', False) is False:
            continue

        if not stage.enabled:
            log.info('stage %s not started - disabled', stage.id)
            continue

        start_run(stage, flow, args=args.get(stage.name, {}))

    data = flow.get_json()

    return data, 201


def get_flows(branch_id, kind, start=0, limit=10, middle=None):
    flows = []
    if kind == 'dev':
        kind = 1
    else:
        kind = 0
    q = Flow.query.filter_by(branch_id=branch_id, kind=kind)
    if middle is None:
        q = q.order_by(desc(Flow.created))
        total = q.count()
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

    base_url = '/artifacts/public/%d' % flow_id

    artifacts = []
    for art in Artifact.query.filter_by(flow=flow, section=consts.ARTIFACTS_SECTION_PUBLIC):
        art = art.get_json()
        art['url'] = urljoin(base_url, art['path'].strip('/'))
        artifacts.append(art)
    return {'items': artifacts, 'total': len(artifacts)}, 200

def create_run(flow_id, run):
    """
    This function creates a new person in the people structure
    based on the passed in person data

    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow not found")

    stage = Stage.query.filter_by(id=run['stage_id']).one_or_none()
    if stage is None:
        abort(404, "Stage not found")

    new_run = start_run(stage, flow, args=run.get('args', {}))

    # Serialize and return the newly created run in the response
    data = new_run.get_json()

    return data, 201


def replay_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    trigger_jobs(run, replay=True)

    data = run.get_json()

    return data, 200


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


def get_run_results(run_id, start=0, limit=10,
                    statuses=None, changes=None,
                    min_age=None, max_age=None,
                    min_instability=None, max_instability=None,
                    test_case_text=None, job=None):
    log.info('filters %s %s %s %s %s %s', statuses, changes, min_age, max_age, min_instability, max_instability)
    q = TestCaseResult.query
    q = q.options(joinedload('test_case'),
                  joinedload('job'),
                  joinedload('job.executor_group'),
                  joinedload('job.executor_used'))
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

    q = q.join('test_case').order_by(asc('name'))
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
                  joinedload('job.executor_group'),
                  joinedload('job.executor_used'))
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


def get_result_history(test_case_result_id, start=0, limit=10):
    tcr = TestCaseResult.query.filter_by(id=test_case_result_id).one_or_none()

    q = TestCaseResult.query
    q = q.options(joinedload('test_case'),
                  joinedload('job'),
                  joinedload('job.executor_group'),
                  joinedload('job.executor_used'))
    q = q.filter_by(test_case_id=tcr.test_case_id)
    q = q.join('job')
    q = q.filter_by(executor_group_id=tcr.job.executor_group_id)
    q = q.join('job', 'run', 'flow', 'branch')
    q = q.filter(Branch.id == tcr.job.run.flow.branch_id)
    q = q.order_by(desc(Flow.created))

    total = q.count()
    q = q.offset(start).limit(limit)
    results = []
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


def get_branch(branch_id):
    branch = Branch.query.filter_by(id=branch_id).one_or_none()
    if branch is None:
        abort(404, "Branch not found")
    return branch.get_json(with_results=True), 200


def get_job_logs(job_id, start=0, limit=200, order=None, filters=None):
    job = Job.query.filter_by(id=job_id).one()
    job_json = job.get_json()

    es_server = os.environ.get('KRAKEN_ELASTICSEARCH_URL', consts.DEFAULT_ELASTICSEARCH_URL)
    es = Elasticsearch(es_server)

    query = {"query": {"bool": {"must": []}}}

    # take only logs from given job
    query["query"]["bool"]["must"].append({"match": {"job": int(job_id)}})

    # take only logs generated explicitly by tool
    query["query"]["bool"]["must"].append({"exists": {"field": "tool"}})

    #filters = {'service': ['tool']}
    filters = {}

    if filters:
        if 'origin' in filters:
            process_name = filters['origin']
            del filters['origin']
            if "^" in process_name or "*" in process_name:
                rx = process_name
            else:
                rx = ".*%s.*" % process_name.lower()
            query["query"]["bool"]["must"].append({"regexp": {"processName": rx}})

        if "level" in filters:
            level = filters['level']
            del filters['level']
            if level == 'error':
                levels = "ERROR"
            elif level == 'warning':
                levels = "ERROR WARNING"
            elif level == 'important':
                levels = "ERROR WARNING IMPORTANT"
            elif level == 'info':
                levels = "ERROR WARNING IMPORTANT INFO"
            elif level == 'debug':
                levels = "ERROR WARNING IMPORTANT INFO DEBUG"
            query["query"]["bool"]["must"].append({"match": {"levelname": levels}})

        if "service" in filters:
            services = filters['service']
            del filters['service']
            if any(services):
                query["query"]["bool"]["must"].append({"terms": {"service": services}})

        if "message" in filters:
            message = filters['message']
            del filters['message']
            if "^" in message or "*" in message:
                rx = message
            else:
                rx = ".*%s.*" % message.lower()
            query["query"]["bool"]["must"].append({"regexp": {"message": rx}})

        if "recent" in filters:
            recent = filters['recent']
            del filters['recent']
            if recent.lower() == 'true':
                start_date = datetime.datetime.now() - datetime.timedelta(days=7)
                query["query"]["bool"]["must"].append(
                    {"range": {"@timestamp": {"gt": start_date.strftime("%Y-%m-%d")}}})

        query["query"]["bool"]["must"].extend([{"match": {k: v}} for k, v in filters.items()])

    query["from"] = start
    query["size"] = limit
    if order is None:
        query["sort"] = {"@timestamp": {"order": "asc"}}  # , "ignore_unmapped": True}}
    elif order in ['asc', 'desc']:
        query["sort"] = {"@timestamp": {"order": order}}
    else:
        query["sort"] = order

    log.info(query)
    try:
        res = es.search(index="logstash*", body=query)
    except:
        # try one more time
        res = es.search(index="logstash*", body=query)

    logs = []
    for hit in res['hits']['hits']:
        l = hit[u'_source']
        entry = dict(time=l[u'@timestamp'],
                     message=l['message'],
                     service=l['service'] if u'service' in l else "",
                     origin=l['processName'] if u'processName' in l else "",
                     host=l['host'],
                     level=l['level'].lower()[:4] if u'level' in l else "info",
                     job=l['job'],
                     tool=l['tool'] if 'tool' in l else "",
                     step=l['step'] if 'step' in l else "")
        logs.append(entry)

    total = res['hits']['total']['value']
    return {'items': logs, 'total': total, 'job': job_json}, 200


def cancel_job(job, note=None):
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    if job.state == consts.JOB_STATE_COMPLETED:
        return
    job.state = consts.JOB_STATE_COMPLETED
    job.completion_status = consts.JOB_CMPLT_SERVER_TIMEOUT
    if note:
        job.notes = note
    job.executor = None
    # TODO: add canceling the job on executor side
    db.session.commit()
    t = bg_jobs.job_completed.delay(job.id)
    log.info('job %s timed out, bg processing: %s', job, t)
