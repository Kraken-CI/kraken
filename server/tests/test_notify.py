import json
from unittest.mock import patch

import pytest

from kraken.server import consts, initdb
from kraken.server.models import db, Project, Branch, Flow, Secret, Stage, AgentsGroup, Agent, Tool
from kraken.server.models import Run, Step, System, Job, RepoChanges, set_setting

from common import create_app

from kraken.server import notify

def test_notify_github_start():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1', user_data={'aaa': 321})
        branch = Branch(name='br', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch,
                      name = 'stag',
                      schema={
                          'notification': {
                              'github': {
                                  'credentials': '#{KK_SECRET_SIMPLE_gh_creds}',
                              }
                          }
                      })
        rc = RepoChanges(data=[{'after': 'sha1',
                                'repo': 'http://gh.com/Kraken-CI/kraken.git'}])
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123}, trigger_data=rc,
                    label='lbl')
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.')
        secret = Secret(project=proj,
                        kind=consts.SECRET_KIND_SIMPLE,
                        name='gh_creds',
                        data={'secret': 'user:token'})
        db.session.commit()

        with patch('requests.post') as rp, patch('kraken.server.notify._get_srv_url', return_value='http://aa.pl'):
            notify.notify(run, 'start')
            rp.assert_called_once()
            assert rp.call_args[0][0] == 'https://api.github.com/repos/Kraken-CI/kraken/statuses/sha1'
            assert rp.call_args[1]['auth'] == ('user', 'token')
            assert 'data' in rp.call_args[1]
            data = rp.call_args[1]['data']
            data = json.loads(data)
            assert data['state'] == 'pending'
            assert data['context'] == 'kraken / stag [lbl]'
            assert data['target_url'] == 'http://aa.pl/runs/%d' % run.id
            assert data['description'] == 'waiting for results'


def test_notify_github_end():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        proj = Project(name='proj-1', user_data={'aaa': 321})
        branch = Branch(name='br', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch,
                      name = 'stag',
                      schema={
                          'notification': {
                              'github': {
                                  'credentials': 'user:token',
                              }
                          }
                      })
        rc = RepoChanges(data=[{'after': 'sha1',
                                'repo': 'http://gh.com/Kraken-CI/kraken.git'}])
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123}, trigger_data=rc,
                    label='lbl')
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.', args={})
        run.regr_cnt = 1
        run.fix_cnt = 2
        run.issues_new = 3
        db.session.commit()

        with patch('requests.post') as rp, patch('kraken.server.notify._get_srv_url', return_value='http://aa.pl'):
            notify.notify(run, 'end')
            rp.assert_called_once()
            assert rp.call_args[0][0] == 'https://api.github.com/repos/Kraken-CI/kraken/statuses/sha1'
            assert rp.call_args[1]['auth'] == ('user', 'token')
            assert 'data' in rp.call_args[1]
            data = rp.call_args[1]['data']
            data = json.loads(data)
            assert data['state'] == 'failure'
            assert data['context'] == 'kraken / stag [lbl]'
            assert data['target_url'] == 'http://aa.pl/runs/%d' % run.id
            assert data['description'] == 'regressions: 1, fixes: 2, new issues: 3'

GH_PUSH = [{"ref": "refs/heads/master", "repo": "https://github.com/Kraken-CI/kraken.git", "after": "453b0586d2455b63a868f81b1cefd6debc3d93c2", "before": "b1678d84ab423c6fce4485cb48e94091faea29af", "pusher": {"name": "godfryd", "email": "godfryd@gmail.com"}, "commits": [
            {"id": "cbcd9949d274d88d3521514bad9231cbffeac2ae", "url": "https://github.com/Kraken-CI/kraken/commit/cbcd9949d274d88d3521514bad9231cbffeac2ae", "added": [], "author": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "message": "improved getting and adding agents groups", "removed": [], "tree_id": "80dcea80f12ff68d257b4dbf59fab0396ed778d1", "distinct": True, "modified": ["server/kraken/server/management.py", "server/kraken/server/schema.py", "ui/src/app/groups-page/groups-page.component.ts"], "committer": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "timestamp": "2023-11-19T09:40:52+01:00"},
            {"id": "b5ab81b9326c808565649f3ac307d571c9ce135d", "url": "https://github.com/Kraken-CI/kraken/commit/b5ab81b9326c808565649f3ac307d571c9ce135d", "added": [], "author": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "message": "fixed getting env vars in branch", "removed": [], "tree_id": "8fabc3b899d931dae674f9feabb351969f87e26b", "distinct": True, "modified": ["server/kraken/server/models.py"], "committer": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "timestamp": "2023-11-19T09:41:05+01:00"},
            {"id": "453b0586d2455b63a868f81b1cefd6debc3d93c2", "url": "https://github.com/Kraken-CI/kraken/commit/453b0586d2455b63a868f81b1cefd6debc3d93c2", "added": [], "author": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "message": "improved presenting duration of job steps", "removed": [], "tree_id": "07f6bfccee26f9b87072163e5a681ae939fe9151", "distinct": True, "modified": ["server/kraken/server/models.py", "ui/src/app/logs-panel/logs-panel.component.html"], "committer": {"name": "Michal Nowikowski", "email": "godfryd@gmail.com", "username": "godfryd"}, "timestamp": "2023-11-19T09:56:55+01:00"}], "trigger": "github-push"}]

GH_PR = [{"repo": "https://github.com/Kraken-CI/kraken.git", "after": "0905154a46fd12f78fd981ec18ac913b6367394d", "action": "opened", "before": "504e67e6d0fd05367e89284677f36bf29afb8758", "sender": {"id": 176567, "url": "https://api.github.com/users/godfryd", "type": "User", "login": "godfryd", "html_url": "https://github.com/godfryd", "avatar_url": "https://avatars.githubusercontent.com/u/176567?v=4"}, "trigger": "github-pull_request", "pull_request": {"id": 1630547580, "url": "https://api.github.com/repos/Kraken-CI/kraken/pulls/318", "base": {"ref": "master", "sha": "504e67e6d0fd05367e89284677f36bf29afb8758"}, "repo": {"id": 280832057, "url": "https://api.github.com/repos/Kraken-CI/kraken", "name": "kraken", "user": {"id": 68497961, "url": "https://api.github.com/users/Kraken-CI", "type": "Organization", "login": "Kraken-CI", "html_url": "https://github.com/Kraken-CI", "avatar_url": "https://avatars.githubusercontent.com/u/68497961?v=4"}}, "head": {"ref": "snyk-upgrade-160424302bef9627fc16d2a157018edc", "sha": "0905154a46fd12f78fd981ec18ac913b6367394d", "repo": {"id": 280832057, "url": "https://api.github.com/repos/Kraken-CI/kraken", "name": "kraken", "git_url": "git://github.com/Kraken-CI/kraken.git", "created_at": "2020-07-19T09:22:37Z", "updated_at": "2023-12-03T23:41:39Z"}, "user": {"id": 68497961, "url": "https://api.github.com/users/Kraken-CI", "type": "Organization", "login": "Kraken-CI", "html_url": "https://github.com/Kraken-CI", "avatar_url": "https://avatars.githubusercontent.com/u/68497961?v=4"}}, "user": {"id": 176567, "type": "User", "login": "godfryd", "html_url": "https://github.com/godfryd", "avatar_url": "https://avatars.githubusercontent.com/u/176567?v=4"}, "title": "[Snyk] Upgrade luxon from 3.3.0 to 3.4.4", "number": 318, "commits": 1, "diff_url": "https://github.com/Kraken-CI/kraken/pull/318.diff", "html_url": "https://github.com/Kraken-CI/kraken/pull/318", "additions": 5, "deletions": 5, "created_at": "2023-12-05T14:45:14Z", "updated_at": "2023-12-05T14:45:14Z", "changed_files": 2}}]

@pytest.mark.parametrize("repo_changes", [GH_PUSH, GH_PR])
def test_notify_discord_end(repo_changes):
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        set_setting('general', 'server_url', 'https://lab.kraken.ci')

        proj = Project(name='Kraken', user_data={'aaa': 321})
        secret = Secret(project=proj,
                        kind=consts.SECRET_KIND_SIMPLE,
                        name='discord_webhook',
                        data={'secret': 'https://discord.com/api/webhooks/1181460671498567741/CFddN6qIAJIhbUP5YUHys0lgxwUe99OzpUAe27M6VA9BIPE0qKhGnUBmvVz43QO3l-1e'})
        branch = Branch(name='main', project=proj, user_data={'aaa': 234}, user_data_ci={'aaa': {'bbb': 234}}, user_data_dev={'aaa': 456})
        stage = Stage(branch=branch,
                      name = 'Build',
                      schema={
                          'notification': {
                              'discord': {
                                  'webhook': '#{secrets.discord_webhook}',
                              }
                          }
                      })
        rc = RepoChanges(data=repo_changes)
        flow = Flow(branch=branch, kind=consts.FLOW_KIND_CI, user_data={'aaa': 123}, trigger_data=rc,
                    label='kk-123')
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.', args={})
        run.regr_cnt = 1
        run.fix_cnt = 2
        run.issues_new = 3
        run = Run(stage=stage, flow=flow, reason={'reason': 'by me'}, label='333.', repo_data=rc)
        run.regr_cnt = 2
        run.fix_cnt = 3
        run.issues_new = 4
        run.jobs_error = 2
        run.jobs_total = 30
        run.tests_passed = 147
        run.tests_total = 200
        db.session.commit()

        #with patch('requests.post') as rp, patch('kraken.server.notify._get_srv_url', return_value='http://aa.pl'):
        if True:
            notify.notify(run, 'end')
            rp.assert_called_once()
            assert rp.call_args[0][0] == 'https://api.github.com/repos/Kraken-CI/kraken/statuses/sha1'
            assert rp.call_args[1]['auth'] == ('user', 'token')
            assert 'data' in rp.call_args[1]
            data = rp.call_args[1]['data']
            data = json.loads(data)
            assert data['state'] == 'pending'
            assert data['context'] == 'kraken / stag [lbl]'
            assert data['target_url'] == 'http://aa.pl/runs/%d' % run.id
            assert data['description'] == 'waiting for results'
