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

import logging
import datetime

from sqlalchemy.orm.attributes import flag_modified

from . import consts
from .models import db, BranchSequence, Flow, Run, Job, Step, AgentsGroup, Tool, Agent, AgentAssignment, System
from .schema import check_and_correct_stage_schema, prepare_secrets, substitute_vars
from . import dbutils

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
    log.info('job %s timed out or canceled, bg processing: %s', job, t, job=job.id)


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


def start_run(stage, flow, reason, args=None, repo_data=None):
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
            lbl_vals = substitute_vars(lbl_vals, run_args)
            if flow.label is None:
                flow.label = lbl_vals.get('flow_label', None)

        # if currently there is not repo data copy it from previous run if it is there
        if not repo_data:
            prev_run = dbutils.get_prev_run(stage.id, flow.kind)
            if prev_run and prev_run.repo_data_id and prev_run.repo_data.data:
                repo_data = prev_run.repo_data
                log.info('new run, taken repo_data from prev run %s', prev_run)

        # create run instance
        run = Run(stage=stage, flow=flow, args=run_args, label=lbl_vals.get('run_label', None), reason=reason, repo_data=repo_data)
        replay = False
        if stage.schema['triggers'].get('manual', False):
            run.state = consts.RUN_STATE_MANUAL
    else:
        # move run back into IN PROGRESS state
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


def create_a_flow(branch, kind, body, trigger_data=None):
    if kind == 'dev':
        kind = 1
    else:
        kind = 0

    args = body.get('args', {})
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
    log.info('created %s flow in branch %s', 'ci' if kind == 0 else 'dev', branch.id)

    reason = dict(reason='manual')

    for stage in branch.stages:
        if stage.deleted:
            continue
        if stage.schema['parent'] != 'root' or stage.schema['triggers'].get('parent', True) is False:
            continue

        if not stage.enabled:
            log.info('stage %s not started - disabled', stage.id)
            continue

        start_run(stage, flow, reason=reason, args=args.get(stage.name, {}))

    return flow


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

    schema_code, schema = check_and_correct_stage_schema(run.stage.branch, run.stage.name, run.stage.schema_code, context)

    run.stage.schema = schema
    run.stage.schema_code = schema_code
    flag_modified(run.stage, 'schema')
    db.session.commit()


def _find_covered_jobs(run):
    covered_jobs = {}
    q = Job.query.filter_by(run=run).filter_by(covered=False)
    for j in q.all():
        key = '%s-%s' % (j.name, j.agents_group_id)
        if key not in covered_jobs:
            covered_jobs[key] = [j]
        else:
            covered_jobs[key].append(j)

    return covered_jobs


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
    if replay:
        covered_jobs = _find_covered_jobs(run)

    # prepare secrets to pass them to substitute in steps
    secrets = prepare_secrets(run)

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
                q = AgentAssignment.query.filter_by(agents_group=agents_group)
                q = q.join('agent')
                q = q.filter(Agent.disabled.is_(False))
                q = q.filter(Agent.authorized.is_(True))
                cnt = q.count()
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
                        fields = substitute_vars(s, args)
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

    # notify
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    t = bg_jobs.notify_about_started_run.delay(run.id)
    log.info('enqueued notification about start of run %s, bg processing: %s', run, t)

    if len(schema['jobs']) == 0 or all_started_erred:
        complete_run(run, now)
