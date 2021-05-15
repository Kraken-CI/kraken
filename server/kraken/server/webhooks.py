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

import json
import hmac
import hashlib
import logging

from flask import Blueprint, request, abort

from .models import Project
from .bg import jobs as bg_jobs
from .utils import log_wrap

log = logging.getLogger(__name__)


@log_wrap('webhooks')
def handle_github_webhook(project_id):
    payload = request.get_data()
    log.info('GITHUB for project_id:%s, payload: %s', project_id, payload)
    event = request.headers.get('X-GitHub-Event')
    if event is None:
        log.warning('missing github event type in request header')
        abort(400, "missing github event type in request header")
    log.info('EVENT %s', event)
    if event not in ['push', 'pull_request']:
        log.info('unsupported event')
        return "", 204

    # check project
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        log.warning('cannot find project %s', project_id)
        abort(400, "Invalid project id")

    if not project.webhooks.get('github_enabled', False):
        log.info('webhooks from github disabled')
        abort(400, "webhooks from github disabled")

    # check secret
    my_secret = None
    if project.webhooks:
        my_secret = project.webhooks.get('github_secret', None)
        if my_secret:
            my_secret = bytes(my_secret, 'ascii')
    if my_secret is not None:
        github_sig = request.headers.get("X-Hub-Signature")
        if github_sig is None:
            log.warning('missing signature in request header')
            abort(400, "missing signature in request header")
        github_digest_parts = github_sig.split("=", 1)
        my_digest = hmac.new(my_secret, payload, hashlib.sha1).hexdigest()

        if len(github_digest_parts) < 2 or github_digest_parts[0] != "sha1" or not hmac.compare_digest(github_digest_parts[1], my_digest):
            log.warning('bad signature %s vs %s, secret %s', github_sig, my_digest, my_secret)
            abort(400, "Invalid signature")

    req = json.loads(payload)

    # trigger running the project flow via celery
    if event == 'push':
        trigger_data = dict(trigger='github-' + event,
                            ref=req['ref'],
                            before=req['before'],
                            after=req['after'],
                            repo=req['repository']['clone_url'],
                            pusher=req['pusher'],
                            commits=req['commits'])
    elif event == 'pull_request':
        if req['action'] not in ['opened', 'synchronize']:
            log.info('unsupported action %s', req['action'])
            return "", 204

        if req['action'] == 'opened' and req['pull_request']['commits'] == 0:
            log.info('pull request with no commits, dropped')
            return "", 204

        if 'before' in req:
            before = req['before']
        else:
            before = req['pull_request']['base']['sha']

        if 'after' in req:
            after = req['after']
        else:
            after = req['pull_request']['head']['sha']

        trigger_data = dict(trigger='github-' + event,
                            action=req['action'],
                            pull_request=req['pull_request'],
                            before=before,
                            after=after,
                            repo=req['repository']['clone_url'],
                            sender=req['sender'])
    t = bg_jobs.trigger_flow.delay(project.id, trigger_data)
    log.info('triggering run for project %s, bg processing: %s', project_id, t)
    return "", 204


def create_blueprint():
    bp = Blueprint('webhooks', __name__)

    bp.add_url_rule('/<int:project_id>/github', view_func=handle_github_webhook, methods=['POST'])

    return bp
