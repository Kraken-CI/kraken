import hmac
import hashlib
import logging

from flask import Blueprint, request, abort

from .models import db, Stage
from .bg import jobs as bg_jobs

log = logging.getLogger(__name__)


def handle_github_webhook(stage_id):
    payload = request.get_data()
    log.info('GITHUB for stage_id:%s, payload: %s', stage_id, payload)
    event = request.headers.get('X-GitHub-Event')
    if event is None:
        log.warn('missing github event type in request header')
        abort(400, "missing github event type in request header")
    log.info('EVENT %s', event)

    # check stage
    stage = Stage.query.filter_by(id=stage_id).one_or_none()
    if stage is None:
        log.warn('cannot find stage %s', stage_id)
        abort(400, "Invalid stage id")

    if not stage.webhooks.get('github_enabled', False):
        log.info('webhooks from github disabled')
        abort(400, "webhooks from github disabled")

    # check secret
    my_secret = None
    if stage.webhooks:
        my_secret = stage.webhooks.get('github_secret', None)
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
    repo_url = req['repository']['clone_url']
    ref = req['ref']
    branch = ref.split('/')[-1]

    # trigger running the stage via celery
    trigger_data = dict(trigger='github-' + event,
                        ref=req['ref'],
                        before=req['before'],
                        after=req['after'],
                        repo='github.com/' + req['repository']['full_name'],
                        pusher=req['pusher'],
                        commits=req['commits'])
    t = bg_jobs.trigger_run.delay(stage.id, trigger_data)
    log.info('triggering run for stage %s, bg processing: %s', stage_id, t)
    return "", 204


def create_blueprint():
    bp = Blueprint('webhooks', __name__)

    bp.add_url_rule('/<int:stage_id>/github', view_func=handle_github_webhook, methods=['POST'])

    return bp
