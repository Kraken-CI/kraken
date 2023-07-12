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

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import desc

from . import consts
from .models import db, BranchSequence, Flow, Run, Job, Step, AgentsGroup, Tool, Agent, AgentAssignment, System
from .schema import check_and_correct_stage_schema, prepare_secrets, substitute_vars, substitute_val, prepare_context
from . import dbutils
from . import kkrq
from . import utils

log = logging.getLogger(__name__)


def complete_run(run, now):
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    run.state = consts.RUN_STATE_COMPLETED
    run.finished = now
    db.session.commit()
    log.info('completed run %s, now: %s', run, run.finished)

    # trigger run analysis
    kkrq.enq(bg_jobs.analyze_run, run.id)
    log.info('run %s completed', run)


def cancel_job(job, note, cmplt_status):
    # job is not un-assigned from agent, this will happen in backend.py
    # when agent will call get_job or any other function
    # or in watchdog.py in _check_agents_keep_alive if agent is not alive
    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
    if job.state == consts.JOB_STATE_COMPLETED:
        return

    log.set_ctx(job=job.id)

    job.completed = utils.utcnow()
    job.state = consts.JOB_STATE_COMPLETED
    job.completion_status = cmplt_status
    job.notes = note
    job.finished = utils.utcnow()
    db.session.commit()
    kkrq.enq(bg_jobs.job_completed, job.id)
    log.info('job %s canceled because: %s', job, note, job=job.id)


def _increment_sequences(branch, stage, kind):
    if stage is None:
        if kind == consts.FLOW_KIND_CI:
            seq1_kind = consts.BRANCH_SEQ_FLOW
            seq1_name = 'KK_FLOW_SEQ'
            seq2_kind = consts.BRANCH_SEQ_CI_FLOW
        else:
            seq1_kind = consts.BRANCH_SEQ_FLOW
            seq1_name = 'KK_FLOW_SEQ'
            seq2_kind = consts.BRANCH_SEQ_DEV_FLOW
        seq2_name = 'KK_CI_DEV_FLOW_SEQ'
    else:
        if kind == consts.FLOW_KIND_CI:
            seq1_kind = consts.BRANCH_SEQ_RUN
            seq1_name = 'KK_RUN_SEQ'
            seq2_kind = consts.BRANCH_SEQ_CI_RUN
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

    vals2 = {'shared': seq1.value, 'own': seq2.value}
    return vals, vals2


def complete_starting_run(run_id):
    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        raise Exception('run %d cannot be found' % run_id)

    log.set_ctx(branch=run.flow.branch_id, flow_kind=run.flow.kind, flow=run.flow_id, run=run.id)

    log.info('complete starting run: %s', run)

    # if this is already executed run then replay it, if this is new, fresh run then do everything from scratch
    if run.state == consts.RUN_STATE_REPLAY:
        # move run back into IN PROGRESS state
        run.state = consts.RUN_STATE_IN_PROGRESS
        replay = True
    else:
        replay = False

        # prepare args
        run_args = run.stage.get_default_args()
        if run.flow.args:
            run_args.update(run.flow.args)
        if run.args is not None:
            run_args.update(run.args)

        # increment sequences
        seq_vals, seq_vals2 = _increment_sequences(run.flow.branch, run.stage, run.flow.kind)
        run_args.update(seq_vals)
        run.seq = seq_vals2

        # prepare flow label if needed
        lbl_vals = {}
        for lbl_field in ['flow_label', 'run_label']:
            label_pattern = run.stage.schema.get(lbl_field, None)
            if label_pattern:
                lbl_vals[lbl_field] = label_pattern
        if lbl_vals:
            ctx = prepare_context(run, run_args)
            lbl_vals, _ = substitute_vars(lbl_vals, run_args, ctx)
            if run.flow.label is None:
                run.flow.label = lbl_vals.get('flow_label', None)

        # if currently there is not repo data copy it from previous run if it is there
        repo_data = run.repo_data
        if not repo_data:
            prev_run = dbutils.get_prev_run(run.stage.id, run.flow.kind)
            if prev_run and prev_run.repo_data_id and prev_run.repo_data.data:
                repo_data = prev_run.repo_data
                log.info('new run, taken repo_data from prev run %s', prev_run)

        # initialize run instance
        run.args = run_args
        run.label = lbl_vals.get('run_label', None)
        run.repo_data = repo_data

        # move run from CREATING to proper state
        if run.stage.schema['triggers'].get('manual', False):
            run.state = consts.RUN_STATE_MANUAL
        else:
            run.state = consts.RUN_STATE_IN_PROGRESS

    db.session.commit()

    # trigger jobs if not manual
    if run.state == consts.RUN_STATE_MANUAL:
        log.info('created manual run %s for stage %s of branch %s - no jobs started yet', run, run.stage, run.stage.branch)
    else:
        # update pointer to last, incomplete, CI flow in the branch
        if run.flow.kind == consts.FLOW_KIND_CI:
            last_flow = run.flow.branch.ci_last_incomplete_flow
            if last_flow is None or last_flow.created < run.flow.created:
                run.flow.branch.ci_last_incomplete_flow = run.flow

        # trigger jobs
        log.info('starting run %s for stage %s of branch %s', run, run.stage, run.stage.branch)
        # TODO: move triggering jobs to background tasks
        trigger_jobs(run, replay=replay)

    return run


def start_run(stage, flow, reason, args=None, repo_data=None):
    # if there was already run for this stage then replay it, otherwise create new one
    run = Run.query.filter_by(stage=stage, flow=flow).one_or_none()
    if run is None:
        # create run instance
        run = Run(stage=stage, flow=flow, args=args, reason=reason, repo_data=repo_data, state=consts.RUN_STATE_CREATING)
    else:
        # move run to REPLAY state
        run.state = consts.RUN_STATE_REPLAY
    db.session.commit()

    log.set_ctx(run=run.id)

    if stage.schema_from_repo_enabled:
        from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel
        kkrq.enq_neck(bg_jobs.refresh_schema_repo, stage.id, run.id, ignore_args=[1])
    else:
        complete_starting_run(run.id)

    return run


def create_a_flow(branch, kind, body, trigger_data=None):
    if kind == 'dev':
        kind = consts.FLOW_KIND_DEV
    else:
        kind = consts.FLOW_KIND_CI

    args = body.get('args', {})
    flow_args = args.get('Common', {})
    branch_name = flow_args.get('BRANCH', branch.branch_name)
    if 'BRANCH' in flow_args:
        del flow_args['BRANCH']

    # increment sequences
    seq_vals, seq_vals2 = _increment_sequences(branch, None, kind)
    flow_args.update(seq_vals)

    flow_args['KK_FLOW_TYPE'] = 'CI' if kind == consts.FLOW_KIND_CI else 'DEV'
    flow_args['KK_BRANCH'] = branch_name if branch_name else 'master'
    flow_args['branch'] = flow_args['KK_BRANCH']

    # create flow instance
    flow = Flow(branch=branch, kind=kind, branch_name=branch_name, args=flow_args, trigger_data=trigger_data,
                seq=seq_vals2)
    db.session.commit()

    log.set_ctx(flow_kind=flow.kind, flow=flow.id)

    log.info('created %s flow %s in branch %s',
             'ci' if kind == 0 else 'dev',
             flow, branch)

    reason = dict(reason='manual')

    for stage in branch.stages:
        if stage.deleted:
            continue
        if stage.schema['parent'] != 'root' or stage.schema['triggers'].get('parent', True) is False:
            continue

        if not stage.enabled:
            log.info('stage %s not started - disabled', stage)
            continue

        start_run(stage, flow, reason=reason, args=args.get(stage.name, {}))

    return flow


def _reeval_schema(run):
    ctx = prepare_context(run, run.args)
    schema_code, schema = check_and_correct_stage_schema(run.stage.branch, run.stage.name, run.stage.schema_code, ctx)

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
            timeout = max(timeout, 60)
    else:
        timeout = consts.DEFAULT_JOB_TIMEOUT

    return timeout


def trigger_jobs(run, replay=False):
    log.info('triggering jobs for run %s', run)

    try:

        # reevaluate schema code
        _reeval_schema(run)

        schema = run.stage.schema

        # find any prev jobs that will be covered by jobs triggered here in this function
        if replay:
            covered_jobs = _find_covered_jobs(run)

        # prepare missing group
        missing_agents_group = AgentsGroup.query.filter_by(name='missing').one_or_none()
        if missing_agents_group is None:
            missing_agents_group = AgentsGroup(name='missing')
            db.session.commit()

        # count how many agents are in each group, if there is 0 for given job then return an error
        agents_count = {}

        agents_needed = set()
        created_systems = {}

        run_ctx = prepare_context(run, run.args)

        # trigger new jobs based on jobs defined in stage schema
        all_started_erred = True
        now = utils.utcnow()
        for j in schema['jobs']:
            # check tools in steps
            tools = []
            tool_not_found = None
            for idx, s in enumerate(j['steps']):
                if '@' in s['tool']:
                    name, ver = s['tool'].split('@')
                    tool = Tool.query.filter_by(name=name, version=ver).one_or_none()
                else:
                    tool = Tool.query.filter_by(name=s['tool']).order_by(desc(Tool.created)).first()
                if tool is None:
                    tool_not_found = s['tool']
                    break
                tools.append(tool)
            if tool_not_found is not None:
                log.warning('cannot find tool %s', tool_not_found)

            envs = j['environments']
            for env in envs:
                # get agents group
                ag_name, _ = substitute_val(env['agents_group'], run.args, run_ctx)
                q = AgentsGroup.query
                q = q.filter_by(project=run.stage.branch.project, name=ag_name)
                agents_group = q.one_or_none()

                if agents_group is None:
                    agents_group = AgentsGroup.query.filter_by(name=ag_name).one_or_none()
                    if agents_group is None:
                        log.warning("cannot find agents group '%s'", ag_name)

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
                    systems = [substitute_val(env['system'], run.args, run_ctx)[0]]
                else:
                    systems = [substitute_val(s, run.args, run_ctx)[0] for s in env['system']]

                for system_name in systems:
                    # prepare system and executor
                    if 'executor' in env:
                        executor = env['executor'].lower()
                    else:
                        executor = 'local'
                    system = System.query.filter_by(name=system_name, executor=executor).one_or_none()
                    sys_key = (system_name, executor)
                    if system is None:
                        system = created_systems.get(sys_key, None)
                    if system is None:
                        system = System(name=system_name, executor=executor)
                        db.session.flush()
                        # this is to avoid doing flush for the same system
                        created_systems[sys_key] = system

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
                            job.notes = "cannot find agents group '%s' in database" % ag_name
                        erred_job = True
                    elif agents_group.deployment and agents_group.deployment['method'] > 0:
                        agents_needed.add(agents_group.id)
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
                            step = Step(job=job, index=idx, tool=tools[idx], fields={}, fields_masked={}, fields_raw=s)
                            evaluate_step_fields(step)

                    # if this is rerun/replay then mark prev jobs as covered
                    if replay:
                        key = '%s-%s' % (j['name'], agents_group.id)
                        if key in covered_jobs:
                            for cj in covered_jobs[key]:
                                cj.covered = True
                                # TODO: we should cancel these jobs if they are still running

                    db.session.commit()
                    log.set_ctx(job=job.id)
                    log.info('created job %s', job.get_json(mask_secrets=True))
                    log.set_ctx(job=None)

    except Exception as ex:
        log.exception('Problem with starting jobs')
        now = utils.utcnow()
        run.started = now
        run.note = "Triggering run's jobs failed: %s" % str(ex)
        complete_run(run, now)
        return

    run.started = now
    run.state = consts.RUN_STATE_IN_PROGRESS  # need to be set in case of replay
    db.session.commit()

    from .bg import jobs as bg_jobs  # pylint: disable=import-outside-toplevel

    # spawn new agents if needed
    if agents_needed:
        for ag_id in agents_needed:
            kkrq.enq_neck(bg_jobs.spawn_new_agents, ag_id)
        log.info('enqueued spawning new agents for run %s', run)

    # notify
    kkrq.enq(bg_jobs.notify_about_started_run, run.id)
    log.info('enqueued notification about start of run %s', run)

    if len(schema['jobs']) == 0 or all_started_erred:
        complete_run(run, now)


def evaluate_step_fields(step):
    run = step.job.run
    # prepare secrets to pass them to substitute in steps
    secrets = prepare_secrets(run)
    args = secrets.copy()
    if run.args:
        args.update(run.args)
    step_ctx = prepare_context(step, args)
    if 'when' in step.fields_raw:
        if not step.fields_raw['when'].startswith('#{'):
            step.fields_raw['when'] = '#{' + step.fields_raw['when'] + '}'
    else:
        step.fields_raw['when'] = '#{was_no_error}'
    flag_modified(step, 'fields_raw')
    fields, fields_masked = substitute_vars(step.fields_raw, args, step_ctx)
    del fields['tool']
    step.fields = fields
    step.fields_masked = fields_masked
    db.session.commit()
