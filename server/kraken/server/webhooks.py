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
import dateutil.parser

from .models import Project
from .bg import jobs as bg_jobs
from . import kkrq

log = logging.getLogger(__name__)


### GITHUB #############

def handle_github_webhook(project_id):
    payload = request.get_data()
    log.info('GITHUB for project_id:%s, payload: %s', project_id, payload)

    # check event
    event = request.headers.get('X-GitHub-Event')
    if event is None:
        log.warning('missing github event type in request header')
        abort(400, "missing github event type in request header")
    log.info('EVENT %s', event)
    if event not in ['push', 'pull_request']:
        msg = 'unsupported event'
        log.info(msg)
        return msg, 204

    # check project
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        log.warning('cannot find project %s', project_id)
        abort(400, "Invalid project id")

    if not project.webhooks or not project.webhooks.get('github_enabled', False):
        log.info('webhooks from github disabled')
        abort(400, "webhooks from github disabled")

    # check secret
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
            log.warning('bad signature %s vs %s', github_sig, my_digest)
            abort(400, "Invalid signature")

    req = json.loads(payload)

    # trigger running the project flow via rq
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
            msg = 'unsupported action %s' % req['action']
            log.info(msg)
            return msg, 204

        if req['action'] == 'opened' and req['pull_request']['commits'] == 0:
            msg = 'pull request with no commits, dropped'
            log.info(msg)
            return msg, 204

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
    kkrq.enq(bg_jobs.trigger_flow, project.id, trigger_data)
    return "", 204


### GITEA #############

def handle_gitea_webhook(project_id):
    payload = request.get_data()
    log.info('GITEA for project_id:%s, payload: %s', project_id, payload)
    event = request.headers.get('X-Gitea-Event')
    signature = request.headers.get("X-Hub-Signature")
    log.info('GITEA event:%s, signature: %s', event, signature)
    return _handle_gitea_webhook(project_id, payload, event, signature)


def _handle_gitea_webhook(project_id, payload, event, signature):
    # check event
    if event is None:
        log.warning('missing gitea event type in request header')
        abort(400, "missing gitea event type in request header")
    log.info('EVENT %s', event)
    if event not in ['push', 'pull_request']:
        msg = 'unsupported event'
        log.info(msg)
        return msg, 204

    # check project
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        log.warning('cannot find project %s', project_id)
        abort(400, "Invalid project id")

    if not project.webhooks or not project.webhooks.get('gitea_enabled', False):
        log.info('webhooks from gitea disabled')
        abort(400, "webhooks from gitea disabled")

    # check secret
    my_secret = project.webhooks.get('gitea_secret', None)
    if my_secret:
        my_secret = bytes(my_secret, 'ascii')
    if my_secret is None:
        msg = 'secret not configured for gitea webhook'
        log.warning(msg)
        return msg, 204
    if signature is None:
        log.warning('missing signature in request header')
        abort(400, "missing signature in request header")
    digest_parts = signature.split("=", 1)
    my_digest = hmac.new(my_secret, payload, hashlib.sha1).hexdigest()

    if len(digest_parts) < 2 or digest_parts[0] != "sha1" or not hmac.compare_digest(digest_parts[1], my_digest):
        log.warning('bad signature %s vs %s', signature, my_digest)
        abort(400, "Invalid signature")

    req = json.loads(payload)

    # trigger running the project flow via rq
    if event == 'push':
        trigger_data = dict(trigger='gitea-' + event,
                            ref=req['ref'],
                            before=req['before'],
                            after=req['after'],
                            repo=req['repository']['clone_url'],
                            pusher=req['pusher'],
                            commits=req['commits'])
    elif event == 'pull_request':
        if req['action'] not in ['opened', 'synchronize', 'synchronized']:
            msg = 'unsupported action %s' % req['action']
            log.info(msg)
            return msg, 204

        if 'before' in req and 'after' in req:
            before = req['before']
            after = req['after']
        else:
            before = req['pull_request']['base']['sha']
            after = req['pull_request']['head']['sha']

        if after == before:
            msg = 'pull request with no commits, dropped'
            log.info(msg)
            return msg, 204

        trigger_data = dict(trigger='gitea-' + event,
                            action=req['action'],
                            pull_request=req['pull_request'],
                            before=before,
                            after=after,
                            repo=req['repository']['clone_url'],
                            sender=req['sender'])
    kkrq.enq(bg_jobs.trigger_flow, project.id, trigger_data)

    return "", 204


### GITLAB #############

def handle_gitlab_webhook(project_id):
    payload = request.get_data()
    log.info('GITLAB for project_id:%s, payload: %s', project_id, payload)
    event = request.headers.get('X-Gitlab-Event')
    token = request.headers.get('X-Gitlab-Token')
    return _handle_gitlab_webhook(project_id, payload, event, token)


def _handle_gitlab_webhook(project_id, payload, event, token):
    # check event
    if event is None:
        log.warning('missing gitlab event type in request header')
        abort(400, "missing gitlab event type in request header")
    log.info('EVENT %s', event)
    if event not in ['Push Hook', 'Merge Request Hook']:
        msg = 'unsupported event'
        log.info(msg)
        return msg, 204

    # check project
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        log.warning('cannot find project %s', project_id)
        abort(400, "Invalid project id")

    if not project.webhooks or not project.webhooks.get('gitlab_enabled', False):
        log.info('webhooks from gitlab disabled')
        abort(400, "webhooks from gitlab disabled")

    # check secret
    my_secret = project.webhooks.get('gitlab_secret', None)
    if my_secret is None:
        log.warning('secret not configured for gitea webhook')
        return "", 204
    if token is None:
        log.warning('missing token in request header')
        abort(400, "missing token in request header")

    if token != my_secret:
        log.warning('bad token %s vs %s', token, my_secret)
        abort(400, "Invalid token")

    req = json.loads(payload)

    # trigger running the project flow via rq
    if event == 'Push Hook':
        trigger_data = dict(trigger='gitlab-' + event,
                            ref=req['ref'],
                            before=req['before'],
                            after=req['after'],
                            repo=req['repository']['git_http_url'],
                            pusher=dict(full_name=req['user_name'],
                                        username=req['user_username'],
                                        email=req['user_email']),
                            commits=req['commits'])
    elif event == 'Merge Request Hook':
        obj = req['object_attributes']
        action = obj['action']
        if action not in ['open', 'update']:
            msg = 'unsupported action %s' % action
            log.info(msg)
            return msg, 204

        if 'oldrev' in obj:
            before = obj['oldrev']
        else:
            before = ''

        after = obj['last_commit']['id']

        if after == before:
            msg = 'merge request with no commits, dropped'
            log.info(msg)
            return msg, 204

        # get base url
        base_url = req['project']['web_url']
        base_url = base_url.rsplit('/', 2)[0]

        trigger_data = dict(trigger='gitlab-' + event,
                            action=action,
                            pull_request=dict(head=dict(ref=obj['source_branch']),
                                              base=dict(ref=obj['target_branch'],
                                                        sha=before),
                                              user=dict(login=req['user']['username'],
                                                        html_url='%s/%s' % (base_url, req['user']['username'])),
                                              html_url=obj['url'],
                                              number=obj['id'],
                                              updated_at=dateutil.parser.parse(obj['updated_at']).isoformat(),
                                              title=obj['title']),
                            before=before,
                            after=after,
                            repo=req['project']['git_http_url'],
                            sender=req['user'])
    kkrq.enq(bg_jobs.trigger_flow, project.id, trigger_data)

    return "", 204


### BLUEPRINT #############

def create_blueprint():
    bp = Blueprint('webhooks', __name__)

    bp.add_url_rule('/<int:project_id>/github', view_func=handle_github_webhook, methods=['POST'])
    bp.add_url_rule('/<int:project_id>/gitea', view_func=handle_gitea_webhook, methods=['POST'])
    bp.add_url_rule('/<int:project_id>/gitlab', view_func=handle_gitlab_webhook, methods=['POST'])

    return bp
