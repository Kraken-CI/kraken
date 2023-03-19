# Copyright 2020-2022 The Kraken Authors
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

from flask import abort
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified

from . import consts
from . import utils
from .models import db, Branch, Flow, Run, Job, TestCaseResult
from .models import TestCase, TestCaseComment, System, AgentsGroup
from . import access

log = logging.getLogger(__name__)


def get_run_results(run_id, start=0, limit=10, sort_field="name", sort_dir="asc",
                    statuses=None, changes=None,
                    min_age=None, max_age=None,
                    min_instability=None, max_instability=None,
                    test_case_text=None, job=None,
                    systems=None, groups=None, token_info=None):

    run = Run.query.filter_by(id=run_id).one_or_none()
    if run is None:
        abort(404, "Run %s not found" % run_id)
    access.check(token_info, run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power user or project viewer roles can view results')

    log.info('filters %s %s %s %s %s %s %s %s %s %s',
             statuses, changes, min_age, max_age, min_instability, max_instability,
             test_case_text, job, systems, groups)
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
    if systems:
        q = q.join('job', 'system').filter(System.id.in_(systems))
    if groups:
        q = q.join('job', 'agents_group').filter(AgentsGroup.id.in_(groups))

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
    elif sort_field == "system":
        q = q.join('job', 'system').order_by(sort_func('name'))
    elif sort_field == "group":
        q = q.join('job', 'agents_group').order_by(sort_func('relevancy'))
    else:
        q = q.join('test_case').order_by(sort_func('name'))

    q = q.offset(start).limit(limit)
    results = []
    for tcr in q.all():
        results.append(tcr.get_json(with_comment=True))
    return {'items': results, 'total': total}, 200


def get_result_history(test_case_result_id, start=0, limit=10, token_info=None):
    tcr = TestCaseResult.query.filter_by(id= test_case_result_id).one_or_none()
    if tcr is None:
        abort(404, "Test case result %s not found" % test_case_result_id)
    access.check(token_info, tcr.job.run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power user or project viewer roles can view results')

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
    q = q.filter(Flow.kind == consts.FLOW_KIND_CI)
    q = q.filter(Flow.created <= tcr.job.run.flow.created)
    q = q.order_by(desc(Flow.created))

    total = q.count()
    q = q.offset(start).limit(limit)
    results = []
    if tcr.job.run.flow.kind == consts.FLOW_KIND_DEV:
        results.append(tcr.get_json(with_extra=True))
    for tcr in q.all():
        results.append(tcr.get_json(with_extra=True))
    return {'items': results, 'total': total}, 200


def get_result(test_case_result_id, token_info=None):
    tcr = TestCaseResult.query.filter_by(id=test_case_result_id).one_or_none()
    if tcr is None:
        abort(404, "Test case result %s not found" % test_case_result_id)

    access.check(token_info, tcr.job.run.stage.branch.project_id, 'view',
                 'only superadmin, project admin, project power user or project viewer roles can view results')

    return tcr.get_json(with_extra=True), 200


def create_or_update_test_case_comment(test_case_result_id, body, token_info=None):
    author = body.get('author', None)
    state = body.get('state', None)
    text = body.get('text', None)
    if author is None:
        abort(400, "Missing author in request")
    if state is None:
        abort(400, "Missing state in request")
    if text is None:
        abort(400, "Missing text in request")

    tcr = TestCaseResult.query.filter_by(id=test_case_result_id).one_or_none()
    if tcr is None:
        abort(404, "Test case result %s not found" % test_case_result_id)

    access.check(token_info, tcr.job.run.stage.branch.project_id, 'pwrusr',
                 'only superadmin, project admin and project power user roles can comment results')

    if tcr.comment:
        tcc = tcr.comment
    else:
        # find if there exists a TestCaseComment for this test case and this branch
        q = TestCaseComment.query
        q = q.filter_by(test_case=tcr.test_case)
        q = q.filter_by(branch=tcr.job.run.flow.branch)
        tcc = q.one_or_none()

        if tcc is None:
            tcc = TestCaseComment(test_case=tcr.test_case,
                                  branch=tcr.job.run.flow.branch,
                                  last_flow=tcr.job.run.flow)
        elif tcc.last_flow.created < tcr.job.run.flow.created:
            tcc.last_flow = tcr.job.run.flow

        tcr.comment = tcc

    # find all other tcrs for the same test case and flow as current tcr
    # and assign this comment to them
    q = TestCaseResult.query
    q = q.filter_by(test_case=tcr.test_case)
    q = q.join('job', 'run', 'flow')
    q = q.filter(Flow.id == tcr.job.run.flow_id)
    for tcr2 in q.all():
        tcr2.comment = tcc

    # adjust relevancy is root cause found
    if (tcc.state not in [consts.TC_COMMENT_BUG_IN_PRODUCT, consts.TC_COMMENT_BUG_IN_TEST] and
        state in [consts.TC_COMMENT_BUG_IN_PRODUCT, consts.TC_COMMENT_BUG_IN_TEST]):
        tcr.relevancy -= 1

    # set user provided values in the comment
    tcc.state = state
    if not tcc.data:
        tcc.data = []
    tcc.data.append({
        'author': author,
        'date': utils.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        'text': text,
        'state': state,
        'tcr': test_case_result_id
    })
    flag_modified(tcc, 'data')
    db.session.commit()

    resp = tcc.get_json()
    resp['data'] = list(reversed(resp['data']))

    return resp, 200


def get_flow_analysis(flow_id, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow %s not found" % flow_id)
    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power user or project viewer roles can view results')

    q = Run.query.filter_by(flow_id=flow_id)

    recs_map = dict(systems={}, groups={})
    stats = {}
    analysis = dict(recs_map=recs_map,
                    stats=stats,
                    total_tests=0)

    total_tests = 0
    for run in q.all():
        log.info('run %s', run)

        if run.stage.name not in stats:
            stats[run.stage.name] = {'run_id': run.id}
        stage = stats[run.stage.name]

        q = TestCaseResult.query
        q = q.options(joinedload('test_case'),
                      joinedload('job'),
                      joinedload('job.agents_group'),
                      joinedload('job.agent_used'))
        q = q.join('job')
        q = q.filter(Job.run_id == run.id, Job.covered.is_(False))

        for tcr in q.all():
            # stage -> group -> system -> config -> component: PASSED: 5, NOT-RUN: 3, TOTAL: 8
            group_name = tcr.job.agents_group.name
            recs_map['groups'][group_name] = tcr.job.agents_group.id
            if group_name not in stage:
                stage[group_name] = {}
            group = stage[group_name]

            system_name = tcr.job.system.name
            recs_map['systems'][system_name] = tcr.job.system.id
            if system_name not in group:
                group[system_name] = {}
            system = group[system_name]

            # config_name = 'default'
            # component = 'all'

            if 'total' not in system:
                system['total'] = 0
            system['total'] += 1

            tcr_res = consts.TC_RESULTS_NAME[tcr.result]
            if tcr_res not in system:
                system[tcr_res] = 0
            system[tcr_res] += 1

            total_tests += 1

    analysis['total_tests'] = total_tests


    return analysis, 200


def get_branch_history(flow_id, limit=30, token_info=None):
    flow = Flow.query.filter_by(id=flow_id).one_or_none()
    if flow is None:
        abort(404, "Flow %s not found", flow_id)

    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power user or project viewer roles can view results')

    if flow.kind != consts.FLOW_KIND_CI:
        abort(400, "Branch history works only for CI, not DEV")

    if limit > 100:
        abort(400, "Cannot get history longer than 100 flows, requested %s", limit)

    q = Flow.query.filter(Flow.created <= flow.created)
    q = q.filter_by(branch_id=flow.branch_id)
    q = q.filter_by(kind=consts.FLOW_KIND_CI)
    q = q.order_by(desc(Flow.created))
    q = q.limit(limit)

    flows = []
    for f in reversed(q.all()):
        if f.summary:
            s = f.summary
        else:
            s = dict(id=f.id, label=f.get_label())

        s['created'] = f.created
        s['finished'] = f.finished

        flows.append(s)

    resp = dict(items=flows, total=len(flows))
    return resp, 200
