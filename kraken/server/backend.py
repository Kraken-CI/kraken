import json
import logging
import datetime

from flask import request

from models import db, Run, Stage, Job, Step, Executor, TestCase, TestCaseResult
import consts

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

def _handle_get_job(executor, req):
    if executor.job is None:
        job = {}
    else:
        job = executor.job.get_json()
        tests = []
        for tcr in executor.job.results:
            tests.append(tcr.test_case.name)
        if tests:
            job['steps'][-1]['tests'] = tests
    log.info('sending job: %s', job)
    return {'job': job}


def _handle_step_result(executor, req):
    if executor.job is None:
        log.error('job in executor %s is missing, reporting some old job %s, step %s',
                  executor, req['job_id'], req['step_idx'])
        return {}

    if executor.job_id != req['job_id']:
        log.error('executor %s is reporting some other job %s',
                  executor, req['job_id'])
        return {}

    try:
        result = req['result']
        step_idx = req['step_idx']
        status = result['status']
        del result['status']
        if status not in list(consts.STEP_STATUS_TO_INT.keys()):
            raise ValueError("unknown status: %s" % status)
    except:
        log.exception('problems with parsing request')
        return {}

    job = executor.job
    step = job.steps[step_idx]
    step.result = result
    step.status = consts.STEP_STATUS_TO_INT[status]
    db.session.commit()

    if 'test-results' in result:
        for tr in result['test-results']:
            q = TestCaseResult.query.filter_by(job=job, result=consts.TC_RESULT_NOT_RUN)
            q = q.join('test_case')
            q = q.filter_by(name=tr['test'])
            tcr = q.one_or_none()
            if tcr is None:
                log.warn('unknown test case reported: %s', tr['test'])
                tc = TestCase.query.filter_by(tool=step.tool, name=tr['test']).one_or_none()
                if tc is None:
                    tc = TestCase(tool=step.tool, name=tr['test'])
                tcr = TestCaseResult(test_case=tc, job=step.job)
            tcr.cmd_line = tr['cmd']
            tcr.result = tr['status']
            db.session.commit()

    job_finished = True
    log.info('checking steps')
    for s in job.steps:
        log.info('%s: %s', s.index, s.status)
        if s.status == consts.STEP_STATUS_DONE:
            continue
        elif s.status == consts.STEP_STATUS_ERROR:
            job_finished = True
            break
        else:
            job_finished = False
            break
    if job_finished:
        job.state = consts.JOB_STATE_EXECUTING_FINISHED
        job.finished = datetime.datetime.utcnow()
        executor.job = None
        db.session.commit()
        log.info('job %s finished by %s', job, executor)

    return {}


def _create_test_records(step, tests):
    tool_test_cases = {}
    q = TestCase.query.filter_by(tool=step.tool)
    for tc in q.all():
        tool_test_cases[tc.name] = tc

    for t in tests:
        tc = tool_test_cases.get(t, None)
        if tc == None:
            tc = TestCase(name=t, tool=step.tool)
        tcr = TestCaseResult(test_case=tc, job=step.job)
    db.session.commit()


def _handle_dispatch_tests(executor, req):
    if executor.job is None:
        log.error('job in executor %s is missing, reporting some old job %s, step %s',
                  executor, req['job_id'], req['step_idx'])
        return {}

    if executor.job_id != req['job_id']:
        log.error('executor %s is reporting some other job %s',
                  executor, req['job_id'])
        return {}

    job = executor.job

    try:
        tests = req['tests']
        step_idx = req['step_idx']
        step = job.steps[step_idx]
    except:
        log.exception('problems with parsing request')
        return {}

    tests_cnt = len(tests)
    if tests_cnt == 0:
        # TODO
        raise NotImplementedError
    elif tests_cnt == 1:
        _create_test_records(step, tests)
        db.session.commit()
        return {'tests': tests}
    else:
        # simple dispatching: divide to 2 jobs, current and new one
        part = tests_cnt // 2
        part1 = tests[:part]
        part2 = tests[part:]

        _create_test_records(step, part1)
        db.session.commit()

        job2 = Job(run=job.run, name=job.name, executor_group=job.executor_group)
        for s in job.steps:
            s2 = Step(job=job2, index=s.index, tool=s.tool, fields=s.fields.copy())
            if s.index == step_idx:
                _create_test_records(s2, part2)
        db.session.commit()

        return {'tests': part1}

def serve_agent_request():
    req = request.get_json()
    # log.info('request headers: %s', request.headers)
    # log.info('request args: %s', request.args)
    log.info('request data: %s', req)

    msg = req['msg']
    address = req['address']

    executor = Executor.query.filter_by(address=address).one_or_none()
    if executor is None:
        log.warn('unknown executor %s', address)
        return json.dumps({})

    response = {}

    if msg == 'get-job':
        response = _handle_get_job(executor, req)

    elif msg == 'in-progres':
        pass

    elif msg == 'step-result':
        response = _handle_step_result(executor, req)

    elif msg == 'dispatch-tests':
        response = _handle_dispatch_tests(executor, req)

    else:
        log.warn('unknown msg: %s', msg)
        response = {}

    return json.dumps(response)
