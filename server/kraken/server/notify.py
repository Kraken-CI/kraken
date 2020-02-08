import logging
import smtplib
from urllib.parse import urljoin
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

from .models import get_setting


log = logging.getLogger(__name__)


SLACK_URL = 'https://slack.com/api/chat.postMessage'


def _notify_slack(run, slack):
    if slack is None:
        return

    channel = slack.get('channel', None)
    if channel is None:
        return

    slack_token = get_setting('notification', 'slack_token')
    if slack_token is None:
        return

    server_url = get_setting('general', 'server_url')
    if server_url is None:
        server_url = 'http://localhost:4200'

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

    log.info('slack resp: %s', r)


def _notify_email(run, email):
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

    server_url = get_setting('general', 'server_url')
    if server_url is None:
        server_url = 'http://localhost:4200'

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

    server.sendmail(smtp_from, recipients, message.as_string())

    server.close()

    log.info('email sent')


def notify(run):
    notification = run.stage.schema.get('notification', None)
    if notification is None:
        return

    changes = notification.get('changes', None)
    if changes is not None:
        slack = changes.get('slack', None)
        try:
            _notify_slack(run, slack)
        except:
            log.exception('IGNORED EXCEPTION')

        email = changes.get('email', None)
        try:
            _notify_email(run, email)
        except:
            log.exception('IGNORED EXCEPTION')
