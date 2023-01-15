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
import logging
from queue import Queue, Empty
from urllib.parse import urlparse
from threading import Thread, Event

from flask import abort, Response
import clickhouse_driver

from . import consts
from . import access
from . import users
from .models import Job


log = logging.getLogger(__name__)

class JobLogDownloader:
    def __init__(self, job_id, step_idx=None):
        self.job_id = job_id
        self.step_idx = step_idx
        self.query = 'select message from logs where job = %d ' % job_id
        if self.step_idx is not None:
            self.query += ' and step = %d ' % self.step_idx
        self.query += 'order by time asc, seq asc'

        ch_url = os.environ.get('KRAKEN_CLICKHOUSE_URL', consts.DEFAULT_CLICKHOUSE_URL)
        o = urlparse(ch_url)
        self.ch = clickhouse_driver.Client(host=o.hostname)

        self.logs_queue = Queue()
        self.finished = Event()
        self.worker = None

    def get_logs(self):
        for l in self.ch.execute_iter(self.query, {'max_block_size': 100000}):
            self.logs_queue.put(l[0] + '\n')

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

    try:
        jld = JobLogDownloader(job_id, None)
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

    try:
        jld = JobLogDownloader(job_id, step_idx)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    log.info('serve_job_log %s', job)
    response = Response(jld.download(), mimetype='plain/text')
    path = 'step_log_%d_%d.txt' % (job_id, step_idx)
    response.headers['Content-Disposition'] = 'attachment; filename=' + path
    return response
