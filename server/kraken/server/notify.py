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
import logging
import smtplib
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

from .models import get_setting
from .schema import prepare_secrets, substitute_vars, prepare_context


log = logging.getLogger(__name__)


SLACK_URL = 'https://slack.com/api/chat.postMessage'


def _get_srv_url():
    server_url = get_setting('general', 'server_url')
    if server_url is None:
        server_url = 'http://localhost:4200'
    return server_url


def _notify_slack(run, event, slack):
    if event == 'start':
        return
    if slack is None:
        return

    channel = slack.get('channel', None)
    if channel is None:
        return

    slack_token = get_setting('notification', 'slack_token')
    if slack_token is None:
        return

    server_url = _get_srv_url()

    text = 'Project <%s|%s>, branch <%s|%s> <%s|%s>, flow <%s|%s>, run <%s|%s %s>'
    text = text % (urljoin(server_url, '/projects/%d' % run.flow.branch.project.id),
                   run.flow.branch.project.name,
                   urljoin(server_url, '/branches/%s' % run.flow.branch.id),
                   run.flow.branch.name,
                   urljoin(server_url, '/branches/%s/%s' % (run.flow.branch.id, 'ci' if run.flow.kind == 0 else 'dev')),
                   'CI' if run.flow.kind == 0 else 'Dev',
                   urljoin(server_url, '/flows/%d' % run.flow.id),
                   run.flow.id,
                   urljoin(server_url, '/runs/%d' % run.id),
                   run.stage.name,
                   run.id)
    if run.regr_cnt > 0:
        text += ', regressions: %d' % run.regr_cnt
    if run.fix_cnt > 0:
        text += ', fixes: %d' % run.fix_cnt
    if run.issues_new > 0:
        text += ', new issues: %d' % run.issues_new

    log.info('slack channel: %s, msg: %s', channel, text)
    data = dict(token=slack_token, channel=channel, text=text)

    # sending post to slack
    r = requests.post(SLACK_URL, data=data)

    log.info('slack resp: %s, %s', r, r.text)


def _notify_email(run, event, email):
    if event == 'start':
        return
    if email is None:
        return
    recipients = email

    smtp_server = get_setting('notification', 'smtp_server')
    if smtp_server is None:
        return

    if ':' in smtp_server:
        smtp_server, smtp_port = smtp_server.split(':')
        smtp_port = int(smtp_port)
    else:
        smtp_port = 0
    smtp_user = get_setting('notification', 'smtp_user')
    smtp_password = get_setting('notification', 'smtp_password')
    smtp_from = get_setting('notification', 'smtp_from')
    if smtp_from is None:
        smtp_from = 'kraken@kraken'
    smtp_tls = get_setting('notification', 'smtp_tls')

    server_url = _get_srv_url()

    html = 'Project <a href="%s">%s</a>, branch <a href="%s">%s</a> <a href="%s">%s</a>, flow <a href="%s">%s</a>, run <a href="%s">%s %s</a>'
    html = html % (urljoin(server_url, '/projects/%d' % run.flow.branch.project.id),
                   run.flow.branch.project.name,
                   urljoin(server_url, '/branches/%s' % run.flow.branch.id),
                   run.flow.branch.name,
                   urljoin(server_url, '/branches/%s/%s' % (run.flow.branch.id, 'ci' if run.flow.kind == 0 else 'dev')),
                   'CI' if run.flow.kind == 0 else 'Dev',
                   urljoin(server_url, '/flows/%d' % run.flow.id),
                   run.flow.id,
                   urljoin(server_url, '/runs/%d' % run.id),
                   run.stage.name,
                   run.id)
    html += '<br>'
    if run.tests_total > 0:
        html += '<br><b>Tests</b><br>'
        html += 'regressions: %d<br>' % run.regr_cnt
        html += 'fixes: %d<br>' % run.fix_cnt
        html += 'passed: %d<br>' % run.tests_passed
        html += 'total: %d<br>' % run.tests_total
        html += 'new: %d<br>' % run.new_cnt

    if run.issues_total > 0:
        html += '<br><b>Issues</b><br>'
        html += 'new issues: %d<br>' % run.issues_new
        html += 'total: %d<br>' % run.issues_total

    html += '<br>-- Kraken'

    subject = '[Kraken] Project %s, branch %s %s, flow %s, run %s %s'
    subject = subject % (run.flow.branch.project.name,
                         run.flow.branch.name,
                         'CI' if run.flow.kind == 0 else 'Dev',
                         run.flow.id,
                         run.stage.name,
                         run.id)
    if run.regr_cnt > 0:
        subject += ', regressions: %d' % run.regr_cnt
    if run.fix_cnt > 0:
        subject += ', fixes: %d' % run.fix_cnt
    if run.issues_new > 0:
        subject += ', new issues: %d' % run.issues_new

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipients
    part = MIMEText(html, "html")
    message.attach(part)

    # sending email to smtp server
    if smtp_tls:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.ehlo()
    if smtp_user and smtp_password:
        server.login(smtp_user, smtp_password)


    log.info("sending email, server: '%s:%s', TLS: %s, user: '%s', password: '%s'",
             smtp_server, str(smtp_port),
             'yes' if smtp_tls else 'no',
             smtp_user if smtp_user else '',
             '*' * len(smtp_password) if smtp_password else '')

    server.sendmail(smtp_from, recipients, message.as_string())

    server.close()

    log.info('email sent')


def _notify_github(run, event, gh):
    if gh is None:
        return
    if not run.flow.trigger_data:
        return

    # prepare github credentials
    creds = gh.get('credentials', None)
    if creds is None:
        log.error('no github credentials')
        return
    creds = creds.split(':')
    if len(creds) != 2:
        log.error('github credentials should have user:token form')
        return
    creds = tuple(creds)  # requests require tuple, not list

    # prepare data for github status
    context = 'kraken / %s [%s]' % (run.stage.name, run.flow.get_label())

    if event == 'start':
        state = 'pending'
        descr = 'waiting for results'
    elif event == 'end':
        state = 'success'
        descr = []
        if run.regr_cnt > 0:
            descr.append('regressions: %d' % run.regr_cnt)
            state = 'failure'
        if run.fix_cnt > 0:
            descr.append('fixes: %d' % run.fix_cnt)
        if run.issues_new > 0:
            descr.append('new issues: %d' % run.issues_new)
            state = 'failure'
        descr = ', '.join(descr)
    else:
        log.error('unsupported event %s', event)
        return

    server_url = _get_srv_url()
    run_url = urljoin(server_url, '/runs/%d' % run.id)

    head = run.flow.trigger_data.data[0]['after']
    repo_parts = run.flow.trigger_data.data[0]['repo'].split('/')
    org = repo_parts[-2]
    repo_name = repo_parts[-1]
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    url = 'https://api.github.com/repos/%s/%s/statuses/%s' % (org, repo_name, head)

    data = {
        'state': state,
        'context': context,
        'target_url': run_url,
        'description': descr
    }

    log.info('GH data %s', data)
    r = requests.post(url, data=json.dumps(data), auth=creds)

    log.info('github resp: %s, %s', r, r.text)


def notify(run, event):
    notification = run.stage.schema.get('notification', None)
    if notification is None:
        return

    # prepare secrets to pass them to substitute in notifications definitions
    args = prepare_secrets(run)
    args.update(run.args)
    ctx = prepare_context(run, args)
    # log.info('notification1 %s', notification)
    notification, _ = substitute_vars(notification, args, ctx)
    # log.info('notification2 %s', notification)

    # slack
    slack = notification.get('slack', None)
    try:
        _notify_slack(run, event, slack)
    except Exception:
        log.exception('IGNORED EXCEPTION')

    # email
    email = notification.get('email', None)
    try:
        _notify_email(run, event, email)
    except Exception:
        log.exception('IGNORED EXCEPTION')

    # github
    github = notification.get('github', None)
    try:
        _notify_github(run, event, github)
    except Exception:
        log.exception('IGNORED EXCEPTION')


def check_email_settings():
    smtp_server = get_setting('notification', 'smtp_server')
    if not smtp_server:
        return 'STMP server address is empty'

    if ':' in smtp_server:
        smtp_server, smtp_port = smtp_server.split(':')
        smtp_port = int(smtp_port)
    else:
        smtp_port = 0
    smtp_user = get_setting('notification', 'smtp_user')
    smtp_password = get_setting('notification', 'smtp_password')
    smtp_tls = get_setting('notification', 'smtp_tls')
    try:
        if smtp_tls:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
    except Exception as ex:
        return str(ex)

    return 'ok'


def check_slack_settings():
    slack_token = get_setting('notification', 'slack_token')
    if not slack_token:
        return 'Slack token is empty'

    # TODO

    return 'ok'
