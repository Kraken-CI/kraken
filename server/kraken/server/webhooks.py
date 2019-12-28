import hmac
import hashlib
import logging

from flask import Blueprint, request, abort

from .models import db, Project
from .bg import jobs as bg_jobs

log = logging.getLogger(__name__)


def handle_github_webhook(project_id):
    payload = request.get_data()
    log.info('GITHUB for project_id:%s, payload: %s', project_id, payload)
    event = request.headers.get('X-GitHub-Event')
    if event is None:
        log.warn('missing github event type in request header')
        abort(400, "missing github event type in request header")
    log.info('EVENT %s', event)

    # check project
    project = Project.query.filter_by(id=project_id).one_or_none()
    if project is None:
        log.warn('cannot find project %s', project_id)
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
            log.warn('missing signature in request header')
            abort(400, "missing signature in request header")
        github_digest_parts = github_sig.split("=", 1)
        my_digest = hmac.new(my_secret, payload, hashlib.sha1).hexdigest()

        if len(github_digest_parts) < 2 or github_digest_parts[0] != "sha1" or not hmac.compare_digest(github_digest_parts[1], my_digest):
            log.warn('bad signature %s vs %s, secret %s', github_sig, my_digest, my_secret)
            abort(400, "Invalid signature")

    req = request.get_json()
    #if event == 'push':

    # trigger running the project flow via celery
    trigger_data = dict(trigger='github-' + event,
                        ref=req['ref'],
                        before=req['before'],
                        after=req['after'],
                        repo=req['repository']['clone_url'],
                        pusher=req['pusher'],
                        commits=req['commits'])
    t = bg_jobs.trigger_flow.delay(project.id, trigger_data)
    log.info('triggering run for project %s, bg processing: %s', project_id, t)
    return "", 204


def create_blueprint():
    bp = Blueprint('webhooks', __name__)

    bp.add_url_rule('/<int:project_id>/github', view_func=handle_github_webhook, methods=['POST'])

    return bp
