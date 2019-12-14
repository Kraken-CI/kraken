import os
import re
import logging
import datetime

from flask import make_response, abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
from elasticsearch import Elasticsearch

from . import consts
from .models import db, Branch, Flow, Run, Stage, Job, Step, ExecutorGroup, Tool, TestCaseResult
from .models import Project

log = logging.getLogger(__name__)


def complete_run(run, now):
    from .bg import jobs as bg_jobs
    log.info('completed run %s', run)
    run.state = consts.RUN_STATE_COMPLETED
    run.finished = now
    db.session.commit()

    # trigger any following stages to currently completed run
    t = bg_jobs.trigger_stages.delay(run.id)
    log.info('run %s completed, trigger the following stages: %s', run, t)

    # establish new flow state
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

    # trigger history of results analysis
    t = bg_jobs.analyze_results_history.delay(run.id)
    log.info('run %s completed, process results: %s', run, t)


def _substitute_vars(fields, args):
    new_fields = {}
    for f, val in fields.items():
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
                    fields = _substitute_vars(s, run.args)
                    del fields['tool']
                    Step(job=job, index=idx, tool=tools[idx], fields=fields)

            if replay:
                key = '%s-%s' % (j['name'], executor_group.id)
                if key in covered_jobs:
                    for cj in covered_jobs[key]:
                        cj.covered = True

            db.session.commit()
            log.info('created job %s', job.get_json())
            started_any = True

    if started_any or len(schema['jobs']) == 0:
        run.started = now
        db.session.commit()

        if len(schema['jobs']) == 0:
            complete_run(run, now)


def create_flow(branch_id, kind, flow):
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

    flow = Flow(branch=branch, kind=kind, branch_name=branch_name, args=flow_args)
    db.session.commit()

    for stage in branch.stages.filter_by(deleted=None):
        if stage.schema['parent'] != 'root' or stage.schema['triggers'].get('parent', False) is False:
            continue

        run = Run(flow=flow, stage=stage, args=args.get(stage.name, {}))
        db.session.commit()

        log.info('triggered run %s for stage %s of branch %s', run, stage, branch)

        trigger_jobs(run)

    data = flow.get_json()

    return data, 201


def get_flows(branch_id, kind, start=0, limit=10):
    flows = []
    if kind == 'dev':
        kind = 1
    else:
        kind = 0
    q = Flow.query.filter_by(branch_id=branch_id, kind=kind)
    q = q.order_by(desc(Flow.created))
    total = q.count()
    q = q.offset(start).limit(limit)
    for flow in q.all():
        flows.append(flow.get_json())
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
        runs.append(runs.get_json())
    return runs, 200


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

    args = run.get('args', {})

    new_run = Run(stage=stage, flow=flow, args=args)
    db.session.commit()

    trigger_jobs(new_run)

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


def get_run_results(run_id, start=0, limit=10):
    q = TestCaseResult.query
    q = q.options(joinedload('test_case'),
                  joinedload('job'),
                  joinedload('job.executor_group'),
                  joinedload('job.executor_used'))
    q = q.join('job')
    q = q.filter(Job.run_id == run_id, Job.covered == False)
    total = q.count()
    q = q.offset(start).limit(limit)
    results = []
    for tcr in q.all():
        results.append(tcr.get_json())
    return {'items': results, 'total': total}, 200


def get_run_jobs(run_id, start=0, limit=10):
    q = Job.query
    q = q.filter_by(run_id=run_id)
    total = q.count()
    q = q.offset(start).limit(limit)
    jobs = []
    for j in q.all():
        jobs.append(j.get_json())
    return {'items': jobs, 'total': total}, 200


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


def get_projects():
    q = Project.query
    projects = []
    for p in q.all():
        projects.append(p.get_json())
    return {'items': projects, 'total': len(projects)}, 200


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

    query["query"]["bool"]["must"].append({"match": {"job": int(job_id)}})

    filters = {'service': ['tool']}

    if filters:
        if 'origin' in filters:
            processName = filters['origin']
            del filters['origin']
            if "^" in processName or "*" in processName:
                rx = processName
            else:
                rx = ".*%s.*" % processName.lower()
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
                query["query"]["bool"]["must"].append({"range": {"@timestamp": {"gt": start_date.strftime("%Y-%m-%d")}}})

        query["query"]["bool"]["must"].extend([{"match": {k: v}} for k, v in filters.items()])

    query["from"] = start
    query["size"] = limit
    if order is None:
        query["sort"] = {"@timestamp": {"order": "asc"}}  # , "ignore_unmapped": True}}
    elif order in ['asc', 'desc']:
        query["sort"] = {"@timestamp": {"order": order}}
    else:
        query["sort"] = order

    try:
        res = es.search(index="logstash*", body=query)
    except:
        # try one more time
        res = es.search(index="logstash*", body=query)
    log.info(query)

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
