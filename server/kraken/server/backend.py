# Copyright 2020-2021 The Kraken Authors
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
import json
import time
import logging

from flask import request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation  # pylint: disable=no-name-in-module
import giturlparse

from .models import db, Job, Step, Agent, TestCase, TestCaseResult, Issue, Secret, Artifact, File
from .models import System
from . import consts
from .bg import jobs as bg_jobs
from . import minioops
from .. import version
from . import kkrq
from . import utils
from . import dbutils
from . import datastore
from . import exec_utils

log = logging.getLogger(__name__)

JOB = {
    "name": "build-tarball",
    "id": 123,
    "steps": [{
        "tool": "git",
        "checkout": "git@gitlab.isc.org:isc-projects/kea.git",
        "branch": "master"
    }, {
        "tool": "shell",
        "cmd": "cd kea && autoreconf -fi && ./configure && make dist"
    }, {
        "tool": "artifacts",
        "type": "file",
        "upload": "aaa-{ver}.tar.gz"
    }]
}


def _left_time(job):
    now = utils.utcnow()
    slip = now - job.assigned
    timeout = job.timeout
    timeout2 = timeout - slip.total_seconds()
    # reduce slightly timeout
    timeout3 = timeout2 * 0.9
    log.info('%s-%s-%s: now: %s, slip:%s, to1: %s, to2: %s, to3: %s',
             job.name, job.system.id, job.agents_group_id,
             now, slip, timeout, timeout2, timeout3)
    return int(timeout3)


def _handle_get_job(agent):
    if agent.job is None:
        return {'job': {}}

    # handle canceling situation
    if agent.job.state == consts.JOB_STATE_COMPLETED:
        job = agent.job
        agent.job = None
        db.session.commit()
        log.set_ctx(job=job.id)
        log.info("unassigned canceled job %s from %s", job, agent)
        log.set_ctx(job=None)
        return {'job': {}}

    log.set_ctx(job=agent.job_id)

    job = agent.job.get_json()

    job['timeout'] = _left_time(agent.job)

    # prepare test list for execution
    tests = []
    for tcr in agent.job.results:
        tests.append(tcr.test_case.name)
    if tests:
        job['steps'][-1]['tests'] = tests

    # attach trigger data to job
    if agent.job.run.flow.trigger_data:
        job['trigger_data'] = agent.job.run.flow.trigger_data.data
    elif agent.job.run.repo_data_id:
        # pick any repo for now (TODO: it should be more sophisticated and handle all repos)
        url = agent.job.run.repo_data.data[0]['repo']
        commits = agent.job.run.repo_data.data[0]['commits']
        job['trigger_data'] = [dict(repo=url,
                                    after=commits[0]['id'])]

    # attach storage info to job
    job['branch_id'] = agent.job.run.flow.branch_id
    job['flow_kind'] = agent.job.run.flow.kind
    job['flow_id'] = agent.job.run.flow_id
    job['run_id'] = agent.job.run_id

    minio_bucket = minioops.get_or_create_minio_bucket_for_artifacts(agent.job.run.flow.branch_id)
    minio_addr, minio_access_key, minio_secret_key = minioops.get_minio_addr()

    # prepare steps
    project = agent.job.run.flow.branch.project
    for step in job['steps']:
        add_minio = False

        # insert secret from ssh-key
        if 'ssh-key' in step:
            value = step['ssh-key']
            secret = Secret.query.filter_by(project=project, name=value, deleted=None).one_or_none()
            if secret is None:
                raise Exception("Secret '%s' does not exist in project %s" % (value, project.id))
            step['ssh-key'] = dict(username=secret.data['username'],
                                   key=secret.data['key'])

        # insert secret from access-token
        if 'access-token' in step:
            value = step['access-token']
            secret = Secret.query.filter_by(project=project, name=value).one_or_none()
            if secret is None:
                raise Exception("Secret '%s' does not exist in project %s" % (value, project.id))
            step['access-token'] = secret.data['secret']

        # custom fields for GIT
        if step['tool'] == 'git':
            # add http url to git
            url = step['checkout']
            url = giturlparse.parse(url)
            if url.valid:
                url = url.url2https
                step['http_url'] = url
            else:
                log.info('invalid git url %s', step['checkout'])

            # add minio info for storing git repo bundle
            add_minio = True
            bucket, folder = minioops.get_or_create_minio_bucket_for_git(step['checkout'], branch_id=agent.job.run.flow.branch_id)
            step['minio_bucket'] = bucket
            step['minio_folder'] = folder

        # custom fields for ARTIFACTS
        if step['tool'] == 'artifacts':
            add_minio = True
            step['minio_bucket'] = minio_bucket
            if 'destination' not in step:
                step['destination'] = '.'

        # custom fields for CACHE
        if step['tool'] == 'cache':
            add_minio = True
            bucket, folders = minioops.get_or_create_minio_bucket_for_cache(agent.job, step)
            step['minio_bucket'] = bucket
            if step['action'] == 'save':
                step['minio_folder'] = folders
            else:
                step['minio_folders'] = folders

        if step['tool_location'].startswith('minio:'):
            add_minio = True

        # add minio details
        if add_minio:
            step['minio_addr'] = minio_addr
            step['minio_access_key'] = minio_access_key
            step['minio_secret_key'] = minio_secret_key

    if not agent.job.started:
        agent.job.started = utils.utcnow()
        agent.job.state = consts.JOB_STATE_ASSIGNED
        db.session.commit()

    # prepare secrets
    secrets = dbutils.get_secret_values(agent.job.run.flow.branch.project)
    job['secrets'] = secrets

    log.set_ctx(job=None)
    return {'job': job}


def _handle_get_job2(agent):
    if agent.job is None:
        return {'job': {}}

    # handle canceling situation
    if agent.job.state == consts.JOB_STATE_COMPLETED:
        job = agent.job
        agent.job = None
        db.session.commit()
        log.set_ctx(job=job.id)
        log.info("unassigned canceled job %s from %s", job, agent)
        log.set_ctx(job=None)
        return {'job': {}}

    log.set_ctx(job=agent.job_id)

    job = agent.job.get_json(with_steps=False)

    job['timeout'] = _left_time(agent.job)

    # attach trigger data to job
    if agent.job.run.flow.trigger_data:
        job['trigger_data'] = agent.job.run.flow.trigger_data.data
    elif agent.job.run.repo_data_id:
        # pick any repo for now (TODO: it should be more sophisticated and handle all repos)
        url = agent.job.run.repo_data.data[0]['repo']
        commits = agent.job.run.repo_data.data[0]['commits']
        job['trigger_data'] = [dict(repo=url,
                                    after=commits[0]['id'])]

    # attach storage info to job
    job['branch_id'] = agent.job.run.flow.branch_id
    job['flow_kind'] = agent.job.run.flow.kind
    job['flow_id'] = agent.job.run.flow_id
    job['run_id'] = agent.job.run_id

    if not agent.job.started:
        agent.job.started = utils.utcnow()
        agent.job.state = consts.JOB_STATE_ASSIGNED
        db.session.commit()

    # prepare secrets
    secrets = dbutils.get_secret_values(agent.job.run.flow.branch.project)
    job['secrets'] = secrets

    log.set_ctx(job=None)
    return {'job': job}


def _handle_get_job_step(agent):
    finish_step = {'job_step': {'finish': True}}

    if agent.job is None:
        finish_step['msg'] = 'job not assigned to agent'
        return finish_step

    # handle canceling situation
    if agent.job.state == consts.JOB_STATE_COMPLETED:
        job = agent.job
        agent.job = None
        db.session.commit()
        log.set_ctx(job=job.id)
        log.info("unassigned canceled job %s from %s", job, agent)
        log.set_ctx(job=None)
        finish_step['msg'] = 'job already completed'
        return finish_step

    job = agent.job

    log.set_ctx(job=job.id)

    step = None
    for s in sorted(job.steps, key=lambda s: s.index):
        # log.info('job %s step %d status: %s', s.job, s.index, consts.STEP_STATUS_NAME.get(s.status, str(s.status)))
        if s.status in [consts.STEP_STATUS_DONE, consts.STEP_STATUS_SKIPPED, consts.STEP_STATUS_ERROR]:
            continue

        log.set_ctx(step=s.index)

        exec_utils.evaluate_step_fields(s)
        log.info('job %s step %d condition %s => %s', s.job, s.index, s.fields_raw['when'], s.fields['when'])
        if s.fields['when'] == 'False':
            log.info('job %s step %d skipped', s.job, s.index)
            s.status = consts.STEP_STATUS_SKIPPED
            db.session.commit()
            continue
        if s.fields['when'] != 'True':
            log.warning('job %s step %d error while evaluating when condition, probably unsupported character was used', s.job, s.index)
            s.status = consts.STEP_STATUS_ERROR
            db.session.commit()
            continue
        log.info('job %s step %d to execute', s.job, s.index)

        step = s
        break

    log.set_ctx(step=None)

    # if no steps to execute then it means that job is finished
    if step is None:
        finish_step['msg'] = 'no steps to execute'
        log.info("job %s no steps to execute -> job completed", job)

        job.state = consts.JOB_STATE_EXECUTING_FINISHED
        job.finished = utils.utcnow()
        agent.job = None

        _destroy_machine_if_needed(agent, job)

        db.session.commit()
        kkrq.enq(bg_jobs.job_completed, job.id)
        log.info('job %s finished by %s', job, agent)

        log.set_ctx(job=None)
        return finish_step

    log.set_ctx(step=step.index)

    #job = agent.job.get_json()
    step = step.get_json()
    step['finish'] = False

    # step['timeout'] = _left_time(agent.job) TODO

    # prepare test list for execution
    # TODO
    #tests = []
    #for tcr in agent.job.results:
    #    tests.append(tcr.test_case.name)
    #if tests:
    #    job['steps'][-1]['tests'] = tests

    # attach trigger data to job
    if agent.job.run.flow.trigger_data:
        step['trigger_data'] = agent.job.run.flow.trigger_data.data
    elif agent.job.run.repo_data_id:
        # pick any repo for now (TODO: it should be more sophisticated and handle all repos)
        url = agent.job.run.repo_data.data[0]['repo']
        commits = agent.job.run.repo_data.data[0]['commits']
        step['trigger_data'] = [dict(repo=url,
                                    after=commits[0]['id'])]

    # attach storage info to job
    step['branch_id'] = agent.job.run.flow.branch_id
    step['flow_kind'] = agent.job.run.flow.kind
    step['flow_id'] = agent.job.run.flow_id
    step['run_id'] = agent.job.run_id

    minio_bucket = minioops.get_or_create_minio_bucket_for_artifacts(agent.job.run.flow.branch_id)
    minio_addr, minio_access_key, minio_secret_key = minioops.get_minio_addr()

    # prepare step special data
    project = agent.job.run.flow.branch.project
    add_minio = False

    # insert secret from ssh-key
    if 'ssh-key' in step:
        value = step['ssh-key']
        secret = Secret.query.filter_by(project=project, name=value, deleted=None).one_or_none()
        if secret is None:
            raise Exception("Secret '%s' does not exist in project %s" % (value, project.id))
        step['ssh-key'] = dict(username=secret.data['username'],
                               key=secret.data['key'])

    # insert secret from access-token
    if 'access-token' in step:
        value = step['access-token']
        secret = Secret.query.filter_by(project=project, name=value).one_or_none()
        if secret is None:
            raise Exception("Secret '%s' does not exist in project %s" % (value, project.id))
        step['access-token'] = secret.data['secret']

    # custom fields for GIT
    if step['tool'] == 'git':
        # add http url to git
        url = step['checkout']
        url = giturlparse.parse(url)
        if url.valid:
            url = url.url2https
            step['http_url'] = url
        else:
            log.info('invalid git url %s', step['checkout'])

        # add minio info for storing git repo bundle
        add_minio = True
        bucket, folder = minioops.get_or_create_minio_bucket_for_git(step['checkout'], branch_id=agent.job.run.flow.branch_id)
        step['minio_bucket'] = bucket
        step['minio_folder'] = folder

    # custom fields for ARTIFACTS
    if step['tool'] == 'artifacts':
        add_minio = True
        step['minio_bucket'] = minio_bucket
        if 'destination' not in step:
            step['destination'] = '.'

    # custom fields for CACHE
    if step['tool'] == 'cache':
        add_minio = True
        bucket, folders = minioops.get_or_create_minio_bucket_for_cache(agent.job, step)
        step['minio_bucket'] = bucket
        if step['action'] == 'save':
            step['minio_folder'] = folders
        else:
            step['minio_folders'] = folders

    if step['tool_location'].startswith('minio:'):
        add_minio = True

    # add minio details
    if add_minio:
        step['minio_addr'] = minio_addr
        step['minio_access_key'] = minio_access_key
        step['minio_secret_key'] = minio_secret_key

    if not agent.job.started:
        agent.job.started = utils.utcnow()
        agent.job.state = consts.JOB_STATE_ASSIGNED
        db.session.commit()

    # prepare secrets
    secrets = dbutils.get_secret_values(agent.job.run.flow.branch.project)
    step['secrets'] = secrets

    log.set_ctx(job=None)
    return {'job_step': step}


def _store_results(job, step, result):
    t0 = time.time()
    q = TestCaseResult.query.filter_by(job=job)
    q = q.options(joinedload('test_case'))
    q = q.join('test_case')
    or_list = []
    results = {}
    for tr in result['test-results']:
        or_list.append(TestCase.name == tr['test'])
        results[tr['test']] = tr
        log.info('looking for existing results for TC: %s', tr)
    q = q.filter(or_(*or_list))

    # update status of existing test case results
    cnt = 0
    for tcr in q.all():
        log.info('updating result for %s', tcr.test_case.name)
        if tcr.test_case.name not in results:
            log.warning('MISSING result')
            continue
        tr = results.pop(tcr.test_case.name)
        tcr.cmd_line = tr['cmd']
        tcr.result = tr['status']
        tcr.values = tr['values'] if 'values' in tr else None
        cnt += 1
    db.session.commit()
    t1 = time.time()
    log.info('reporting %s existing test records took %ss', cnt, (t1 - t0))

    # create test case results if they didnt exist
    tool_test_cases = {}
    q = TestCase.query.filter_by(tool=step.tool)
    for tc in q.all():
        tool_test_cases[tc.name] = tc
    for tc_name, tr in results.items():
        tc = tool_test_cases.get(tc_name, None)
        if tc is None:
            tc = TestCase(name=tc_name, tool=step.tool)
        TestCaseResult(test_case=tc, job=step.job,
                       cmd_line=tr['cmd'],
                       result=tr['status'],
                       values=tr['values'] if 'values' in tr else None)
    db.session.commit()
    t2 = time.time()
    log.info('reporting %s new test records took %ss', len(results), (t2 - t1))


def _store_issues(job, result):
    t0 = time.time()
    for issue in result['issues']:
        issue_type = 0
        if issue['type'] in consts.ISSUE_TYPES_CODE:
            issue_type = consts.ISSUE_TYPES_CODE[issue['type']]
        else:
            log.warning('unknown issue type: %s', issue['type'])
        extra = {}
        for k, v in issue.items():
            if k not in ['line', 'column', 'path', 'symbol', 'message']:
                extra[k] = v
        Issue(issue_type=issue_type, line=issue['line'], column=issue['column'], path=issue['path'], symbol=issue['symbol'],
              message=issue['message'][:511], extra=extra, job=job)
    db.session.commit()
    t1 = time.time()
    log.info('reporting %s issues took %ss', len(result['issues']), (t1 - t0))


def _store_artifacts(job, step):
    t0 = time.time()
    flow = job.run.flow
    if not flow.artifacts:
        flow.artifacts = dict(public=dict(size=0, count=0, entries=[]),
                              private=dict(size=0, count=0))
    if not flow.artifacts_files:
        flow.artifacts_files = []

    run = job.run
    if not run.artifacts:
        run.artifacts = dict(public=dict(size=0, count=0, entries=[]),
                             private=dict(size=0, count=0))
    if not run.artifacts_files:
        run.artifacts_files = []

    public = step.fields.get('public', False)
    report_entry = step.fields.get('report_entry', None)
    if report_entry:
        public = True
        flow.artifacts['public']['entries'].append(report_entry)
        run.artifacts['public']['entries'].append(report_entry)

    if public:
        section = 'public'
        section_id = consts.ARTIFACTS_SECTION_PUBLIC
    else:
        section = 'private'
        section_id = consts.ARTIFACTS_SECTION_PRIVATE

    for artifact in step.result['artifacts']:
        flow.artifacts[section]['size'] += artifact['size']
        flow.artifacts[section]['count'] += 1

        run.artifacts[section]['size'] += artifact['size']
        run.artifacts[section]['count'] += 1

        if section == 'public':
            report_entry = artifact.get('report_entry', None)
            if report_entry:
                flow.artifacts['public']['entries'].append(report_entry)
                run.artifacts['public']['entries'].append(report_entry)

        path = artifact['path']
        f = File.query.filter_by(path=path).one_or_none()
        if f is None:
            f = File(path=path)
        Artifact(file=f, flow=flow, run=run, size=artifact['size'], section=section_id)

    flag_modified(flow, 'artifacts')
    flag_modified(run, 'artifacts')
    db.session.commit()

    t1 = time.time()
    log.info('reporting %s artifacts took %ss', len(step.result['artifacts']), (t1 - t0))


def _handle_data(job, step, result):
    data = result['data']
    return datastore.handle_data(job, step, data)


def _destroy_machine_if_needed(agent, job):
    to_destroy = False

    # check if cloud machine should be destroyed now
    ag = dbutils.find_cloud_assignment_group(agent)
    if ag:
        # aws ec2
        if ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
            depl = ag.deployment['aws']

            if depl and 'destruction_after_jobs' in depl and int(depl['destruction_after_jobs']) > 0:
                max_jobs = int(depl['destruction_after_jobs'])
                q = Job.query.filter_by(agent_used=agent)
                q = q.filter(Job.finished.isnot(None))
                q = q.filter(Job.finished > agent.created)
                jobs_num = q.count()
                log.info('JOB %s, num %d, max %d', job, jobs_num, max_jobs)
                if jobs_num >= max_jobs:
                    to_destroy = True

        # aws ecs fargate
        elif ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE:
            log.info('ECS FARGATE JOB %s - destroying task: %d', job, agent.id)
            to_destroy = True

        # azure vm
        elif ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
            depl = ag.deployment['azure_vm']

            if depl and 'destruction_after_jobs' in depl and int(depl['destruction_after_jobs']) > 0:
                max_jobs = int(depl['destruction_after_jobs'])
                q = Job.query.filter_by(agent_used=agent)
                q = q.filter(Job.finished.isnot(None))
                q = q.filter(Job.finished > agent.created)
                jobs_num = q.count()
                log.info('JOB %s, num %d, max %d', job, jobs_num, max_jobs)
                if jobs_num >= max_jobs:
                    to_destroy = True

        # kubernetes
        elif ag.deployment['method'] == consts.AGENT_DEPLOYMENT_METHOD_K8S:
            log.info('K8S JOB %s - destroying pod: %d', job, agent.id)
            to_destroy = True

    # schedule destruction if needed
    if to_destroy:
        agent.disabled = True
        kkrq.enq(bg_jobs.destroy_machine, agent.id)


def _handle_step_result(agent, req):
    response = {}
    if agent.job is None:
        log.error('job in agent %s is missing, reporting some old job %s, step %s',
                  agent, req['job_id'], req['step_idx'])
        return response

    if agent.job_id != req['job_id']:
        log.error('agent %s is reporting some other job %s',
                  agent, req['job_id'])
        return response

    log.set_ctx(job=agent.job_id)

    try:
        result = req['result']
        step_idx = req['step_idx']
        status = result['status']
        del result['status']
        if status not in consts.STEP_STATUS_TO_INT:
            log.set_ctx(job=None)
            raise ValueError("unknown status: %s" % status)
    except Exception:
        log.exception('problems with parsing request')
        log.set_ctx(job=None)
        return response

    job = agent.job
    step = job.steps[step_idx]
    step.result = result
    step.status = consts.STEP_STATUS_TO_INT[status]

    # handle canceling situation
    if job.state == consts.JOB_STATE_COMPLETED:
        agent.job = None
        db.session.commit()
        log.info("canceling job %s on %s", job, agent)
        response['cancel'] = True
        log.set_ctx(job=None)
        return response

    db.session.commit()

    # store test results
    if 'test-results' in result:
        _store_results(job, step, result)

    # store issues
    if 'issues' in result:
        _store_issues(job, result)

    # store artifacts
    if 'artifacts' in result:
        _store_artifacts(job, step)

    # set, update or get data
    if 'data' in result:
        _handle_data(job, step, result)

    # check if all steps are done so job is finised
    job_finished = True
    log.info('checking steps')
    for s in job.steps:
        log.info('%s: %s', s.index, consts.STEP_STATUS_NAME[s.status]
                 if s.status in consts.STEP_STATUS_NAME else s.status)
        if s.status in [consts.STEP_STATUS_DONE, consts.STEP_STATUS_SKIPPED]:
            continue
        if s.status == consts.STEP_STATUS_ERROR:
            job_finished = True
            break
        job_finished = False
        break
    if job_finished:
        job.state = consts.JOB_STATE_EXECUTING_FINISHED
        job.finished = utils.utcnow()
        agent.job = None

        _destroy_machine_if_needed(agent, job)

        db.session.commit()
        kkrq.enq(bg_jobs.job_completed, job.id)
        log.info('job %s finished by %s', job, agent)
    else:
        response['timeout'] = _left_time(job)

    log.set_ctx(job=None)
    return response


def _handle_step_result2(agent, req):
    response = {}
    if agent.job is None:
        log.error('job in agent %s is missing, reporting some old job %s, step %s',
                  agent, req['job_id'], req['step_idx'])
        return response

    if agent.job_id != req['job_id']:
        log.error('agent %s is reporting some other job %s',
                  agent, req['job_id'])
        return response

    log.set_ctx(job=agent.job_id)

    try:
        result = req['result']
        step_idx = req['step_idx']
        status = result['status']
        del result['status']
        if status not in consts.STEP_STATUS_TO_INT:
            log.set_ctx(job=None)
            raise ValueError("unknown status: %s" % status)
    except Exception:
        log.exception('problems with parsing request')
        log.set_ctx(job=None)
        return response

    job = agent.job
    step = job.steps[step_idx]
    step.result = result
    step.status = consts.STEP_STATUS_TO_INT[status]

    # handle canceling situation
    if job.state == consts.JOB_STATE_COMPLETED:
        agent.job = None
        db.session.commit()
        log.info("canceling job %s on %s", job, agent)
        response['cancel'] = True
        log.set_ctx(job=None)
        return response

    db.session.commit()

    # store test results
    if 'test-results' in result:
        _store_results(job, step, result)

    # store issues
    if 'issues' in result:
        _store_issues(job, result)

    # store artifacts
    if 'artifacts' in result:
        _store_artifacts(job, step)

    # set, update or get data
    if 'data' in result:
        _handle_data(job, step, result)

    response['timeout'] = _left_time(job)

    log.set_ctx(job=None)
    return response


def _create_test_records(step, tests):
    t0 = time.time()
    tool_test_cases = {}
    q = TestCase.query.filter_by(tool=step.tool)
    for tc in q.all():
        tool_test_cases[tc.name] = tc

    for t in tests:
        tc = tool_test_cases.get(t, None)
        if tc is None:
            tc = TestCase(name=t, tool=step.tool)
        TestCaseResult(test_case=tc, job=step.job)
    db.session.commit()
    t1 = time.time()
    log.info('creating %s test records took %ss', len(tests), (t1 - t0))


def _handle_dispatch_tests(agent, req):
    if agent.job is None:
        log.error('job in agent %s is missing, reporting some old job %s, step %s',
                  agent, req['job_id'], req['step_idx'])
        return {}

    if agent.job_id != req['job_id']:
        log.error('agent %s is reporting some other job %s',
                  agent, req['job_id'])
        return {}

    job = agent.job

    # handle canceling situation
    if job.state == consts.JOB_STATE_COMPLETED:
        agent.job = None
        db.session.commit()
        log.info("canceling job %s on %s", job, agent)
        return {'cancel': True}

    try:
        tests = req['tests']
        step_idx = req['step_idx']
        step = job.steps[step_idx]
    except Exception:
        log.exception('problems with parsing request')
        return {}

    tests_cnt = len(tests)

    if len(set(tests)) != tests_cnt:
        log.warning('there are tests duplicates')
        return {}

    if tests_cnt == 0:
        # TODO
        raise NotImplementedError

    if tests_cnt == 1 or 'autosplit' not in step.fields or not step.fields['autosplit']:
        _create_test_records(step, tests)
        db.session.commit()
        return {'tests': tests}

    # simple dispatching: divide to 2 jobs, current and new one
    part = tests_cnt // 2
    part1 = tests[:part]
    part2 = tests[part:]

    _create_test_records(step, part1)
    db.session.commit()

    # new timeout reduced by nearly a half
    timeout = int(job.timeout * 0.6)
    timeout = max(timeout, 60)

    # create new job and its steps
    job2 = Job(run=job.run, name=job.name, agents_group=job.agents_group, system=job.system, timeout=timeout)
    for s in job.steps:
        s2 = Step(job=job2, index=s.index, tool=s.tool, fields=s.fields.copy())
        if s.index == step_idx:
            _create_test_records(s2, part2)
    db.session.commit()

    return {'tests': part1}


def _handle_host_info(agent, req):  # pylint: disable=unused-argument
    log.info('HOST INFO %s', req['info'])

    system = req['info']['system']

    sys = None
    if system.isdigit():
        # agent has already identified system so find its name
        sys_id = int(system)
        sys = System.query.filter_by(id=sys_id).one_or_none()
        if sys is not None:
            # if this is real system id then substitute it
            req['info']['system'] = sys.name

    agent.host_info = req['info']
    db.session.commit()

    resp = dict(agent_id=agent.id)

    if sys:
        # agent has already identified system so it doesn't need to be created
        return resp

    try:
        System(name=system, executor='local')
        db.session.commit()
    except IntegrityError as e:
        if not isinstance(e.orig, UniqueViolation):
            log.exception('IGNORED')

    return resp


def _handle_keep_alive(agent, req):  # pylint: disable=unused-argument
    job = agent.job

    # handle canceling situation
    if job and job.state == consts.JOB_STATE_COMPLETED:
        agent.job = None
        db.session.commit()
        log.info("canceling job %s on %s", job, agent)
        return {'cancel': True}

    return {}


def _handle_unknown_agent(address, ip_address, agent):
    try:
        new = False
        if agent:
            now = utils.utcnow()
            if agent.deleted:
                log.info('undeleting agent %s with address %s', agent, address)
                agent.deleted = None
                agent.created = now
            agent.authorized = False
            agent.ip_address = ip_address
            agent.last_seen = now
        else:
            agent = Agent(name=address, address=address, authorized=False, ip_address=ip_address, last_seen=utils.utcnow())
            new = True
        db.session.commit()
        if new:
            log.info('created new agent instance %s for address %s', agent, address)
    except Exception as e:
        log.warning('IGNORED EXCEPTION: %s', str(e))


def _serve_agent_request():
    log.reset_ctx()
    req = request.get_json()
    # log.info('request headers: %s', request.headers)
    # log.info('request remote_addr: %s', request.remote_addr)
    # log.info('request args: %s', request.args)
    log.info('request data: %s', str(req)[:200])

    msg = req['msg']
    address = req['address']
    if address is None:
        address = request.remote_addr
    # log.info('agent address: %s', address)

    agent = Agent.query.filter_by(address=address).one_or_none()
    if agent is None or agent.deleted:
        log.warning('unknown agent %s', address)
        _handle_unknown_agent(address, request.remote_addr, agent)
        return json.dumps({'unauthorized': True})

    agent.last_seen = utils.utcnow()
    db.session.commit()

    if not agent.authorized:
        log.warning('unauthorized agent %s from %s', address, request.remote_addr)
        return json.dumps({'unauthorized': True})

    response = {}

    if msg == consts.AGENT_MSG_GET_JOB:
        response = _handle_get_job(agent)

        clickhouse_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', consts.DEFAULT_CLICKHOUSE_ADDR)
        response['cfg'] = dict(clickhouse_addr=clickhouse_addr)
        response['version'] = version.version

    elif msg == consts.AGENT_MSG_GET_JOB2:
        response = _handle_get_job2(agent)

        clickhouse_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', consts.DEFAULT_CLICKHOUSE_ADDR)
        response['cfg'] = dict(clickhouse_addr=clickhouse_addr)
        response['version'] = version.version

    elif msg == consts.AGENT_MSG_GET_JOB_STEP:
        response = _handle_get_job_step(agent)

        clickhouse_addr = os.environ.get('KRAKEN_CLICKHOUSE_ADDR', consts.DEFAULT_CLICKHOUSE_ADDR)
        response['cfg'] = dict(clickhouse_addr=clickhouse_addr)
        response['version'] = version.version

    elif msg == consts.AGENT_MSG_STEP_RESULT:
        response = _handle_step_result(agent, req)

    elif msg == consts.AGENT_MSG_STEP_RESULT2:
        response = _handle_step_result2(agent, req)

    elif msg == consts.AGENT_MSG_DISPATCH_TESTS:
        response = _handle_dispatch_tests(agent, req)

    elif msg == consts.AGENT_MSG_HOST_INFO:
        response = _handle_host_info(agent, req)

    elif msg == consts.AGENT_MSG_KEEP_ALIVE:
        response = _handle_keep_alive(agent, req)

    else:
        log.warning('unknown msg: %s', msg)
        response = {}

    log.info('sending response: %s', str(response)[:200])
    return json.dumps(response)


def serve_agent_request():
    try:
        return _serve_agent_request()
    except Exception:
        db.session.rollback()
        db.session.close()
        raise
