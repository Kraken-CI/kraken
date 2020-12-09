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
from queue import Queue, Empty
from threading import Thread, Event

from flask import abort, Response
from elasticsearch import Elasticsearch

from . import consts
from .models import Job


log = logging.getLogger(__name__)


class JobLogDownloader:
    def __init__(self, job_id, timeout=0.01):

        es_server = os.environ.get('KRAKEN_ELASTICSEARCH_URL', consts.DEFAULT_ELASTICSEARCH_URL)
        self.es = Elasticsearch(es_server)

        query = {"query": {"bool": {"must": []}}}

        # take only logs from given job
        query["query"]["bool"]["must"].append({"match": {"job": int(job_id)}})

        # take only logs generated explicitly by tool
        query["query"]["bool"]["must"].append({"exists": {"field": "tool"}})

        query["size"] = 1000
        query["sort"] = [{"@timestamp": {"order": "asc"}},
                         {"_id": "desc"}]

        self.query = query

        self.timeout = timeout

        self.logs_queue = Queue()
        self.finished = Event()
        self.worker = None

    def get_logs(self):
        while True:
            try:
                res = self.es.search(index="logstash*", body=self.query)
            except:
                # try one more time
                res = self.es.search(index="logstash*", body=self.query)

            if len(res['hits']['hits']) == 0:
                break

            logs = ''
            l = None
            for hit in res['hits']['hits']:
                l = hit
                # TODO: log format
                logs += l[u'_source']['message'] + '\n'

            if l is not None:
                ts = l['sort'][0]
                l_id = l['sort'][1]
                self.query['search_after'] = [int(ts), l_id]

            self.logs_queue.put(logs)

        self.logs_queue.join()   # wait for all blocks in the queue to be marked as processed
        self.finished.set() # mark streaming as finished

    def send_logs(self):
        while not self.finished.is_set():
            try:
                yield self.logs_queue.get(timeout=self.timeout)
                self.logs_queue.task_done()
            except Empty:
                self.finished.wait(self.timeout)
        self.worker.join()

    def download(self, ):
        self.worker = Thread(target=self.get_logs, args=())
        self.worker.start()
        return self.send_logs()


def serve_job_log(job_id):
    job = Job.query.filter_by(id=job_id).one_or_none()
    if job is None:
        abort(404, "Job not found")

    try:
        jld = JobLogDownloader(job_id)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    log.info('serve_job_log %s', job)
    response = Response(jld.download(), mimetype='plain/text')
    path = 'job_log_%d.txt' % job.id
    response.headers['Content-Disposition'] = 'attachment; filename=' + path
    return response
