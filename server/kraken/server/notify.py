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

import sys
import json
import logging
import smtplib
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

from .models import get_setting
from .schema import prepare_secrets, substitute_vars, prepare_context
from . import utils


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


def _notify_discord(run, event, discord):
    if event == 'start':
        return
    if discord is None:
        return

    webhook = discord.get('webhook', None)
    if webhook is None:
        return

    server_url = _get_srv_url()

    if run.jobs_error and run.jobs_error > 0:
        embed_color = 15158332
        status = 'erred'
    else:
        embed_color = 3066993
        status = 'succeeded'

    title = "%s flow %s: %s %s" % (
        'CI' if run.flow.kind == 0 else 'Dev',
        run.flow.get_label(),
        run.stage.name,
        status)

    description = 'Branch [%s](%s), %s [flows](%s), flow [%s](%s)'
    description %= (run.flow.branch.name,
                    urljoin(server_url, '/branches/%s' % run.flow.branch.id),
                    'CI' if run.flow.kind == 0 else 'Dev',
                    urljoin(server_url, '/branches/%s/%s' % (run.flow.branch.id, 'ci' if run.flow.kind == 0 else 'dev')),
                    run.flow.get_label(),
                    urljoin(server_url, '/flows/%d' % run.flow.id))

    if run.repo_data and run.repo_data.data:
        description += ', git '
        rc = run.repo_data.data[0]

        # prepare repo url
        repo_url = rc['repo']
        if repo_url and repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        commits = rc.get('commits', None)
        pr = rc.get('pull_request', None)

        # prepare diff url
        start_commit = ''
        last_commit = ''
        if commits:
            start_commit = rc['before']
            last_commit = rc['after']
        elif pr:
            start_commit = pr['base']['sha']
            last_commit = rc['after']

        if start_commit and last_commit:
            diff_url = f'{repo_url}/compare/{start_commit}...{last_commit}'

        if repo_url:
            description += f'[repo]({repo_url})'
        if diff_url:
            if repo_url:
                description += ', '
            else:
                description += '\n'
            description += f' [diff]({diff_url})'

        if commits and len(commits) > 0:
            description += '\nPush:'
            for c in commits:
                if c.get('url', None):
                    c_url = c['url']
                else:
                    c_url = repo_url + '/commit/' + c['commit']
                description += f"\n[{c['id'][:8]}]({c_url}) "
                description += f"{c['author']['name']}, "
                description += c['message'][:100]

        elif pr:
            description += '\nPull Request'
            description += f" [#{pr['number']}]({pr['html_url']})"
            description += f" by {pr['user']['login']}\n"
            description += f"{pr['title']}\n"
            description += f"branch: {pr['head']['ref']}\n"
            description += f"commits: {pr['commits']}"


    fields = [{
	'name': 'Jobs erred',
	'value': f'{run.jobs_error}/{run.jobs_total}',
	'inline': True,
    }]

    if run.tests_total > 0:
        ratio = run.tests_passed * 100 / float(run.tests_total)
        fields.append({
	    'name': 'Tests',
	    'value': f'{ratio:.1f}%, {run.tests_passed}/{run.tests_total}',
	    'inline': True,
        })

    if run.regr_cnt > 0 or run.fix_cnt > 0 or run.issues_new > 0:
        fields.append({
	    'name': '\u200b',
	    'value': '\u200b',
	    'inline': False,
        })

    if run.regr_cnt > 0:
        fields.append({
            "name": "Regressions",
            "value": '%d' % run.regr_cnt,
            "inline": True
        })
    if run.fix_cnt > 0:
        fields.append({
            "name": "Fixes",
            "value": '%d' % run.fix_cnt,
            "inline": True
        })
    if run.issues_new > 0:
        fields.append({
            "name": "New Issues",
            "value": '%d' % run.issues_new,
            "inline": True
        })

    data = {'embeds': [{
        "avatar_url": "https://lab.kraken.ci/favicon.png",
        "color": embed_color,
        "author": {
            "name": f'Project {run.flow.branch.project.name}',
            "url": urljoin(server_url, '/projects/%d' % run.flow.branch.project.id),
            "icon_url": "https://lab.kraken.ci/favicon.png"
        },
        "title": title,
        "url": urljoin(server_url, '/runs/%d' % run.id),
        "description": description,
        "fields": fields,
        "timestamp": utils.utcnow().isoformat()
    }]}

    log.info('discord webhook: %s/..., data: %s', webhook.rsplit('/', 1)[0], data)

    # sending post to discord
    r = requests.post(webhook, json=data)

    log.info('discord resp: %s, %s', r, r.text)


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
        log.warning('IGNORED', exc_info=sys.exc_info())

    # email
    email = notification.get('email', None)
    try:
        _notify_email(run, event, email)
    except Exception:
        log.warning('IGNORED', exc_info=sys.exc_info())

    # github
    github = notification.get('github', None)
    try:
        _notify_github(run, event, github)
    except Exception:
        log.warning('IGNORED', exc_info=sys.exc_info())

    # discord
    discord = notification.get('discord', None)
    try:
        _notify_discord(run, event, discord)
    except Exception:
        log.warning('IGNORED', exc_info=sys.exc_info())


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
