# Copyright 2023 The Kraken Authors
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
from urllib.parse import urlparse

import clickhouse_driver
from flask import abort

from . import consts
from . import access
from .models import Branch, Flow, Run, Job, Agent


def get_clickhouse_url():
    ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
    return ch_url


def get_clickhouse():
    ch_url = get_clickhouse_url()
    o = urlparse(ch_url)
    ch = clickhouse_driver.Client(host=o.hostname)
    return ch


def prepare_logs_query(branch_id=None, flow_kind=None, flow_id=None, run_id=None, job_id=None, step_idx=None,
                       agent_id=None, services=None, level=None, token_info=None):
    if branch_id is None and flow_id is None and run_id is None and job_id is None and agent_id is None:
        access.check(token_info, '', 'admin',
                     'only superadmin can get services logs')

    if branch_id is None and flow_kind is not None:
        abort(400, "if flow_kind is provided then branch_id must be provided as well")

    if job_id is None and step_idx is not None:
        abort(400, "if step_idx is provided then job_id must be provided as well")

    cols_to_skip = set()

    if step_idx is not None:
        cols_to_skip.add('step_idx')

    if job_id is not None:
        job = Job.query.filter_by(id=job_id).one_or_none()
        if job is None:
            abort(404, "Job not found")
        access.check(token_info, job.run.stage.branch.project_id, 'view',
                     'only superadmin, project admin, project power and project viewer user roles can get job logs')
        cols_to_skip.add('job')
        cols_to_skip.add('run')
        cols_to_skip.add('flow')
        cols_to_skip.add('flow_kind')
        cols_to_skip.add('branch')

    elif run_id is not None:
        run = Run.query.filter_by(id=run_id).one_or_none()
        if run is None:
            abort(404, "Run not found")
        access.check(token_info, run.stage.branch.project_id, 'view',
                     'only superadmin, project admin, project power and project viewer user roles can get run logs')
        cols_to_skip.add('run')
        cols_to_skip.add('flow')
        cols_to_skip.add('flow_kind')
        cols_to_skip.add('branch')

    elif flow_id is not None:
        flow = Flow.query.filter_by(id=flow_id).one_or_none()
        if flow is None:
            abort(404, "Flow not found")
        access.check(token_info, flow.branch.project_id, 'view',
                     'only superadmin, project admin, project power and project viewer user roles can get flow logs')
        cols_to_skip.add('flow')
        cols_to_skip.add('flow_kind')
        cols_to_skip.add('branch')

    elif branch_id is not None:
        branch = Branch.query.filter_by(id=branch_id).one_or_none()
        if branch is None:
            abort(404, "Branch not found")
        access.check(token_info, branch.project_id, 'view',
                     'only superadmin, project admin, project power and project viewer user roles can get branch logs')
        cols_to_skip.add('branch')

    if agent_id is not None:
        agent = Agent.query.filter_by(id=agent_id).one_or_none()
        if agent is None:
            abort(404, "Agent not found")
        access.check(token_info, '', 'admin',
                     'only superadmin can get agent logs')
        cols_to_skip.add('agent')

    params = {}

    where_clauses = []
    if branch_id is not None:
        where_clauses.append('branch = %(branch_id)d')
        params['branch_id'] = branch_id
        if flow_kind is not None:
            where_clauses.append('flow_kind = %(flow_kind)d')
            params['flow_kind'] = flow_kind
    if flow_id is not None:
        where_clauses.append('flow = %(flow_id)d')
        params['flow_id'] = flow_id
    if run_id is not None:
        where_clauses.append('run = %(run_id)d')
        params['run_id'] = run_id
    if job_id is not None:
        where_clauses.append('job = %(job_id)d')
        params['job_id'] = job_id
        if step_idx is not None:
            where_clauses.append('step_idx = %(step_idx)d')
            params['step_idx'] = step_idx
    if agent_id is not None:
        where_clauses.append('agent = %(agent_id)d')
        params['agent_id'] = agent_id

    where_services = []
    if services:
        cols_to_skip.add('agent')
        if len(services) == 1:
            cols_to_skip.add('service')

        for idx, s in enumerate(services):
            param = 'service%d' % idx
            if '/' in s:
                s, t = s.split('/')
                tparam = 'tool%d' % idx
                where_services.append("(service = %%(%s)s and tool = %%(%s)s)" % (param, tparam))
                params[param] = s
                params[tparam] = t
            else:
                where_services.append("service = %%(%s)s" % param)
                params[param] = s
        where = " or ".join(where_services)
        where = "(" + where + ") "
        where_clauses.append(where)

    if level:
        level = level.upper()
        if level == 'ERROR':
            lq = "level = 'ERROR'"
        elif level == 'WARNING':
            lq = "level in ('WARNING', 'ERROR')"
        else:
            lq = "level in ('INFO', 'WARNING', 'ERROR')"
        where_clauses.append(lq)

    if where_clauses:
        where_clause = 'where ' + ' and '.join(where_clauses)
    else:
        where_clause = ''

    columns = ['time', 'message', 'service', 'host', 'path', 'lineno', 'level',
               'branch', 'flow_kind','flow', 'run', 'job', 'tool', 'step', 'agent']
    for col in cols_to_skip:
        columns.remove(col)
    columns = ','.join(columns)

    return columns, where_clause, params
