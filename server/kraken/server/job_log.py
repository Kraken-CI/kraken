# Copyright 2020-2023 The Kraken Authors
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
from queue import Queue, Empty
from threading import Thread, Event

from flask import request, abort, Response
from . import access
from . import users
from .models import Job
from . import chops
from . import utils


log = logging.getLogger(__name__)

class LogDownloader:
    def __init__(self, columns, query, params=None):
        self.columns = columns
        self.query = query
        self.params = params
        self.ch = chops.get_clickhouse()
        self.logs_queue = Queue()
        self.finished = Event()
        self.worker = None

    def get_logs(self):
        self.logs_queue.put(self.columns + '\n')
        for line_items in self.ch.execute_iter(self.query, self.params, settings={'max_block_size': 100000}):
            line = ' '.join([str(i) for i in line_items])
            self.logs_queue.put(line + '\n')

        self.logs_queue.join()  # wait for all blocks in the queue to be marked as processed
        self.finished.set()  # mark streaming as finished

    def send_logs(self):
        while not self.finished.is_set():
            try:
                yield self.logs_queue.get(timeout=0.01)
                self.logs_queue.task_done()
            except Empty:
                self.finished.wait(0.01)
        self.worker.join()

    def download(self, ):
        self.worker = Thread(target=self.get_logs)
        self.worker.start()
        return self.send_logs()


def serve_job_log(job_id):
    job_id = int(job_id)
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    token_info = users.get_token_info_from_request()
    if not token_info:
        abort(401, "Missing Authorization header or kk_session_token cookie")
    access.check(token_info, job.run.flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power user and project viewer roles can fetch job logs')

    query = 'SELECT message FROM logs WHERE job = %d ' % job_id
    query += 'ORDER BY time ASC, seq ASC'

    try:
        jld = LogDownloader('message', query)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    log.info('serve_job_log %s', job)
    response = Response(jld.download(), mimetype='plain/text')
    path = 'job_log_%d.txt' % job.id
    response.headers['Content-Disposition'] = 'attachment; filename=' + path
    return response


def serve_step_log(job_id, step_idx):
    job_id = int(job_id)
    step_idx = int(step_idx)
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    token_info = users.get_token_info_from_request()
    if not token_info:
        abort(401, "Missing Authorization header or kk_session_token cookie")
    access.check(token_info, job.run.flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power user and project viewer roles can fetch job logs')

    query = 'SELECT message FROM logs WHERE job = %d ' % job_id
    query += ' AND step = %d ' % step_idx
    query += 'ORDER BY time ASC, seq ASC'

    try:
        jld = LogDownloader('message', query)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    log.info('serve_job_log %s', job)
    response = Response(jld.download(), mimetype='plain/text')
    path = 'step_log_%d_%d.txt' % (job_id, step_idx)
    response.headers['Content-Disposition'] = 'attachment; filename=' + path
    return response


def serve_any_log():
    token_info = users.get_token_info_from_request()
    branch_id = request.args.get('branch_id', default=None, type=int)
    flow_kind = request.args.get('flow_kind', default=None, type=int)
    flow_id = request.args.get('flow_id', default=None, type=int)
    run_id = request.args.get('run_id', default=None, type=int)
    job_id = request.args.get('job_id', default=None, type=int)
    step_idx = request.args.get('step_id', default=None, type=int)
    agent_id = request.args.get('agent_id', default=None, type=int)
    services = request.args.getlist('services')
    level = request.args.get('level', default=None, type=int)

    columns, where_clause, params = chops.prepare_logs_query(
        branch_id, flow_kind, flow_id, run_id, job_id, step_idx,
        agent_id, services, level, token_info)

    query = f'SELECT {columns} FROM logs {where_clause} '
    query += 'ORDER BY time ASC, seq ASC'

    log.info('log query: %s', query)

    try:
        jld = LogDownloader(columns, query, params)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    # log.info('kraken_log %s', job)
    response = Response(jld.download(), mimetype='plain/text')
    now = utils.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    path = 'kraken_log_%s.txt' % now
    response.headers['Content-Disposition'] = 'attachment; filename=' + path
    return response
