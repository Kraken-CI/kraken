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
from urllib.parse import urljoin, urlparse

from flask import abort
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from elasticsearch import Elasticsearch
import clickhouse_driver

from . import consts
from .models import db, Branch, Flow, Run, Stage, Job, Step, AgentsGroup, Tool, TestCaseResult
from .models import TestCase, Issue, Artifact, AgentAssignment, BranchSequence, System
from .schema import check_and_correct_stage_schema, SchemaError

log = logging.getLogger(__name__)


def complete_run(run, now):
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    run.state = consts.RUN_STATE_COMPLETED
    run.finished = now
    db.session.commit()
    log.info('completed run %s, now: %s', run, run.finished)

    # trigger run analysis
    t = bg_jobs.analyze_run.delay(run.id)
    log.info('run %s completed, analyze run: %s', run, t)


def _substitute_vars(fields, args):
    new_fields = {}
    for f, val in fields.items():
        if isinstance(val, dict):
            new_fields[f] = _substitute_vars(val, args)
            continue
        if not isinstance(val, str):
            new_fields[f] = val
            continue

        for var in re.findall(r'#{[A-Za-z_ ]+}', val):
            name = var[2:-1]
            if name in args:
                arg_val = args[name]
                if  not isinstance(arg_val, str):
                    raise Exception("value '%s' of '%s' should have string type but has '%s'" % (str(arg_val), name, str(type(arg_val))))
                val = val.replace(var, arg_val)
        new_fields[f] = val
    return new_fields


def _setup_schema_context(run):
    ctx = {
        'is_ci': run.flow.kind == 0,
        'is_dev': run.flow.kind == 1,
        'run_label': run.label,
        'flow_label': run.flow.label,
    }
    return ctx


def _reeval_schema(run):
    context = _setup_schema_context(run)

    try:
        schema_code, schema = check_and_correct_stage_schema(run.stage.branch, run.stage.name, run.stage.schema_code, context)
    except SchemaError as e:
        abort(400, str(e))
    run.stage.schema = schema
    run.stage.schema_code = schema_code
    flag_modified(run.stage, 'schema')
    db.session.commit()


def _find_covered_jobs(run):
    covered_jobs = {}
    if replay:
        q = Job.query.filter_by(run=run).filter_by(covered=False)
        for j in q.all():
            key = '%s-%s' % (j.name, j.agents_group_id)
            if key not in covered_jobs:
                covered_jobs[key] = [j]
            else:
                covered_jobs[key].append(j)

    return covered_jobs


def _prepare_secrets(run):
    secrets = {}
    for s in run.stage.branch.project.secrets:
        if s.deleted:
            continue
        if s.kind == consts.SECRET_KIND_SSH_KEY:
            name = "KK_SECRET_USER_" + s.name
            secrets[name] = s.data['username']
            name = "KK_SECRET_KEY_" + s.name
            secrets[name] = s.data['key']
        elif s.kind == consts.SECRET_KIND_SIMPLE:
            name = "KK_SECRET_SIMPLE_" + s.name
            secrets[name] = s.data['secret']

    return secrets


def _establish_timeout_for_job(j, run, system, agents_group):
    if agents_group is not None:
        job_key = "%s-%d-%d" % (j['name'], system.id, agents_group.id)
        if run.stage.timeouts and job_key in run.stage.timeouts:
            # take estimated timeout if present
            timeout = run.stage.timeouts[job_key]
        else:
            # take initial timeout from schema, or default one
            timeout = int(j.get('timeout', consts.DEFAULT_JOB_TIMEOUT))
            if timeout < 60:
                timeout = 60
    else:
        timeout = consts.DEFAULT_JOB_TIMEOUT

    return timeout


def trigger_jobs(run, replay=False):
    log.info('triggering jobs for run %s', run)

    # reevaluate schema code
    _reeval_schema(run)

    schema = run.stage.schema

    # find any prev jobs that will be covered by jobs triggered here in this function
    covered_jobs = _find_covered_jobs(run)

    # prepare secrets to pass them to substitute is steps
    secrets = _prepare_secrets(run)

    # prepare missing group
    missing_agents_group = AgentsGroup.query.filter_by(name='missing').one_or_none()
    if missing_agents_group is None:
        missing_agents_group = AgentsGroup(name='missing')
        db.session.commit()

    # count how many agents are in each group, if there is 0 for given job then return an error
    agents_count = {}

    # trigger new jobs based on jobs defined in stage schema
    all_started_erred = True
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
            # get agents group
            q = AgentsGroup.query
            q = q.filter_by(project=run.stage.branch.project, name=env['agents_group'])
            agents_group = q.one_or_none()

            if agents_group is None:
                agents_group = AgentsGroup.query.filter_by(name=env['agents_group']).one_or_none()
                if agents_group is None:
                    log.warning("cannot find agents group '%s'", env['agents_group'])

            # get count of agents in the group
            if agents_group is not None and agents_group.name not in agents_count:
                cnt = AgentAssignment.query.filter_by(agents_group=agents_group).count()
                #log.info("agents group '%s' count is %d", agents_group.name, cnt)
                agents_count[agents_group.name] = cnt

            if not isinstance(env['system'], list):
                systems = [env['system']]
            else:
                systems = env['system']

            for system_name in systems:
                # prepare system and executor
                if 'executor' in env:
                    executor = env['executor'].lower()
                else:
                    executor = 'local'
                system = System.query.filter_by(name=system_name, executor=executor).one_or_none()
                if system is None:
                    system = System(name=system_name, executor=executor)
                    db.session.flush()

                # get timeout
                timeout = _establish_timeout_for_job(j, run, system, agents_group)

                # create job
                job = Job(run=run, name=j['name'], agents_group=agents_group, system=system, timeout=timeout)

                erred_job = False
                if tool_not_found:
                    job.state = consts.JOB_STATE_COMPLETED
                    job.completion_status = consts.JOB_CMPLT_MISSING_TOOL_IN_DB
                    job.notes = "cannot find tool '%s' in database" % tool_not_found
                    erred_job = True
                if agents_group is None:
                    job.agents_group = missing_agents_group
                    if job.state != consts.JOB_STATE_COMPLETED:
                        job.state = consts.JOB_STATE_COMPLETED
                        job.completion_status = consts.JOB_CMPLT_MISSING_AGENTS_GROUP
                        job.notes = "cannot find agents group '%s' in database" % env['agents_group']
                    erred_job = True
                elif agents_count[agents_group.name] == 0:
                    if job.state != consts.JOB_STATE_COMPLETED:
                        job.state = consts.JOB_STATE_COMPLETED
                        job.completion_status = consts.JOB_CMPLT_NO_AGENTS
                        job.notes = "there are no agents in group '%s' - add some agents" % agents_group.name
                    erred_job = True

                if not erred_job:
                    all_started_erred = False
                    # substitute vars in steps
                    for idx, s in enumerate(j['steps']):
                        args = secrets.copy()
                        args.update(run.args)
                        fields = _substitute_vars(s, args)
                        del fields['tool']
                        Step(job=job, index=idx, tool=tools[idx], fields=fields)

                # if this is rerun/replay then mark prev jobs as covered
                if replay:
                    key = '%s-%s' % (j['name'], agents_group.id)
                    if key in covered_jobs:
                        for cj in covered_jobs[key]:
                            cj.covered = True
                            # TODO: we should cancel these jobs if they are still running

                db.session.commit()
                log.info('created job %s', job.get_json())

    run.started = now
    run.state = consts.RUN_STATE_IN_PROGRESS  # need to be set in case of replay
    db.session.commit()

    if len(schema['jobs']) == 0 or all_started_erred:
        complete_run(run, now)


def start_run(stage, flow, args=None):
    # if there was already run for this stage then replay it, otherwise create new one
    replay = True
    run = Run.query.filter_by(stage=stage, flow=flow).one_or_none()
    if run is None:
        # prepare args
        run_args = stage.get_default_args()
        if flow.args:
            run_args.update(flow.args)
        if args is not None:
            run_args.update(args)

        # increment sequences
        seq_vals = _increment_sequences(flow.branch, stage, flow.kind)
        run_args.update(seq_vals)

        # prepare flow label if needed
        lbl_vals = {}
        for lbl_field in ['flow_label', 'run_label']:
            label_pattern = stage.schema.get(lbl_field, None)
            if label_pattern:
                lbl_vals[lbl_field] = label_pattern
        if lbl_vals:
            lbl_vals = _substitute_vars(lbl_vals, run_args)
            if flow.label is None:
                flow.label = lbl_vals.get('flow_label', None)

        # create run instance
        run = Run(stage=stage, flow=flow, args=run_args, label=lbl_vals.get('run_label', None))
        replay = False
        if stage.schema['triggers'].get('manual', False):
            run.state = consts.RUN_STATE_MANUAL
    else:
        run.state = consts.RUN_STATE_IN_PROGRESS
    db.session.commit()

    # trigger jobs if not manual
    if run.state == consts.RUN_STATE_MANUAL:
        log.info('created manual run %s for stage %s of branch %s - no jobs started yet', run, stage, stage.branch)
    else:
        log.info('starting run %s for stage %s of branch %s', run, stage, stage.branch)
        # TODO: move triggering jobs to background tasks
        trigger_jobs(run, replay=replay)

    return run


def _increment_sequences(branch, stage, kind):
    if stage is None:
        if kind == 0:  # CI
            seq1_kind = consts.BRANCH_SEQ_FLOW
            seq1_name = 'KK_FLOW_SEQ'
            seq2_kind = consts.BRANCH_SEQ_CI_FLOW
        else:
            seq1_kind = consts.BRANCH_SEQ_FLOW
            seq1_name = 'KK_FLOW_SEQ'
            seq2_kind = consts.BRANCH_SEQ_CI_FLOW
        seq2_name = 'KK_CI_DEV_FLOW_SEQ'
    else:
        if kind == 0:  # CI
            seq1_kind = consts.BRANCH_SEQ_RUN
            seq1_name = 'KK_RUN_SEQ'
            seq2_kind = consts.BRANCH_SEQ_DEV_RUN
        else:
            seq1_kind = consts.BRANCH_SEQ_RUN
            seq1_name = 'KK_RUN_SEQ'
            seq2_kind = consts.BRANCH_SEQ_DEV_RUN
        seq2_name = 'KK_CI_DEV_RUN_SEQ'

    seq1 = BranchSequence.query.filter_by(branch=branch, stage=stage, kind=seq1_kind).one()
    seq1.value = BranchSequence.value + 1
    seq2 = BranchSequence.query.filter_by(branch=branch, stage=stage, kind=seq2_kind).one()
    seq2.value = BranchSequence.value + 1
    db.session.commit()

    vals = {}
    vals[seq1_name] = str(seq1.value)
    vals[seq2_name] = str(seq2.value)
    return vals


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

    # increment sequences
    seq_vals = _increment_sequences(branch, None, kind)
    flow_args.update(seq_vals)

    flow_args['KK_FLOW_TYPE'] = 'CI' if kind == 0 else 'DEV'
    flow_args['KK_BRANCH'] = branch_name if branch_name is not None else 'master'

    # create flow instance
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

    base_url = '/artifacts/public/f/%d/' % flow_id

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


def run_run_jobs(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    if run.state == consts.RUN_STATE_MANUAL:
        replay = False
    else:
        replay = True

    trigger_jobs(run, replay=replay)

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
    q = q.filter_by(agents_group_id=tcr.job.agents_group_id)
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


def _get_job_logs_from_es(job_id, limit=200, order=None, filters=None, search_after=None):
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

    query["size"] = limit
    if order is None:
        query["sort"] = [{"@timestamp": {"order": "asc"}}]  # , "ignore_unmapped": True}}
    elif order in ['asc', 'desc']:
        query["sort"] = [{"@timestamp": {"order": order}}]
    else:
        query["sort"] = [order]
    query["sort"].append({"_id": "desc"})

    if search_after:
        ts, _id = search_after.split(',')
        query['search_after'] = [int(ts), _id]

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
    bookmarks = None
    if len(res['hits']['hits']) > 0:
        bookmarks = {
            'first': [res['hits']['hits'][0]['sort'][0], res['hits']['hits'][0]['sort'][1]],
            'last': [res['hits']['hits'][-1]['sort'][0], res['hits']['hits'][-1]['sort'][1]]
        }
    return {'items': logs, 'total': total, 'job': job_json, 'bookmarks': bookmarks}, 200


def _get_job_logs_from_ch(job_id, start=0, limit=200, order=None, filters=None):
    if order not in [None, 'asc', 'desc']:
        abort(400, "incorrect order value: %s" % str(order))

    job = Job.query.filter_by(id=job_id).one()
    job_json = job.get_json()

    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)

    query = "select count(*) from logs where job = %d" % job_id
    resp = ch.execute(query)
    total = resp[0][0]

    if order is None:
        order = 'asc'

    query = "select time,message,service,host,level,job,tool,step from logs where job = %d and tool != '' order by time %s limit %d, %d"
    query %= (job_id, order, start, limit)

    rows = ch.execute(query)

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


# def get_job_logs(job_id, limit=200, order=None, filters=None, search_after=None):
def get_job_logs(job_id, start=0, limit=200, order=None, filters=None):
    return _get_job_logs_from_ch(job_id, start, limit, order, filters)


def cancel_job(job, note, cmplt_status):
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    if job.state == consts.JOB_STATE_COMPLETED:
        return
    job.completed = datetime.datetime.utcnow()
    job.state = consts.JOB_STATE_COMPLETED
    job.completion_status = cmplt_status
    if note:
        job.notes = note
    db.session.commit()
    t = bg_jobs.job_completed.delay(job.id)
    log.info('job %s timed out or canceled, bg processing: %s', job, t)


def cancel_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run not found")

    for job in run.jobs:
        cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)

    return {}


def delete_job(job_id):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    cancel_job(job, 'canceled by user', consts.JOB_CMPLT_USER_CANCEL)

    return {}
