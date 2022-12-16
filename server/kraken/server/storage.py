#!/usr/bin/env python3

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
import logging
import mimetypes
from queue import Queue, Empty
from threading import Thread, Event

from flask import abort, Response
import minio

from .models import Run, Flow
from . import users
from . import access
from . import consts


log = logging.getLogger('storage')


class MinioDownloader:
    def __init__(self, bucket_name, timeout=0.01):
        minio_addr = os.environ.get('KRAKEN_MINIO_ADDR', consts.DEFAULT_MINIO_ADDR)
        root_user = os.environ['MINIO_ROOT_USER']
        root_password = os.environ['MINIO_ROOT_PASSWORD']

        self.mc = minio.Minio(minio_addr, access_key=root_user, secret_key=root_password, secure=False)
        found = self.mc.bucket_exists(bucket_name)
        if not found:
            raise Exception('missing %s minio bucket' % bucket_name)

        self.bucket_name = bucket_name

        self.timeout = timeout

        self.bytes = Queue()
        self.finished = Event()
        self.worker = None

    def get_bytes(self, filename):
        resp = self.mc.get_object(self.bucket_name, filename)
        for chunk in resp.stream():
            self.bytes.put(chunk)
        resp.release_conn()
        self.bytes.join()   # wait for all blocks in the queue to be marked as processed
        self.finished.set() # mark streaming as finished

    def send_bytes(self):
        while not self.finished.is_set():
            try:
                yield self.bytes.get(timeout=self.timeout)
                self.bytes.task_done()
            except Empty:
                self.finished.wait(self.timeout)
        self.worker.join()

    def download(self, filename):
        self.worker = Thread(target=self.get_bytes, args=(filename,))
        self.worker.start()
        return self.send_bytes()


def serve_artifact(store_type, flow_id, run_id, path):
    log.info('path %s, %s, %s, %s', store_type, flow_id, run_id, path)

    if store_type not in ['public', 'report']:
        abort(400, "Not supported store type: %s" % store_type)

    if flow_id:
        flow = Flow.query.filter_by(id=int(flow_id)).one_or_none()
        if flow is None:
            abort(404, "Flow not found")

        runs = []
        for r in flow.runs:
            runs.append(r.id)
        runs.sort()
        run_id = runs[-1]
    else:
        run = Run.query.filter_by(id=int(run_id)).one_or_none()
        if run is None:
            abort(404, "Run not found")
        flow = run.flow


    token_info = users.get_token_info_from_request()
    if not token_info:
        abort(401, "Missing Authorization header or kk_session_token cookie")
    access.check(token_info, flow.branch.project_id, 'view',
                 'only superadmin, project admin, project power user and project viewer roles can fetch artifacts')

    mt, _ = mimetypes.guess_type(path)
    if mt is None:
        mt = 'application/octet-stream'

    bucket_name = '%08d' % flow.branch_id
    mc_dl = MinioDownloader(bucket_name)

    path = os.path.join(str(flow.id), str(run_id), path)
    resp = Response(mc_dl.download(path), mimetype=mt)

    return resp


def serve_flow_artifact(store_type, flow_id, path):
    return serve_artifact(store_type, flow_id, None, path)


def serve_run_artifact(store_type, run_id, path):
    return serve_artifact(store_type, None, run_id, path)
