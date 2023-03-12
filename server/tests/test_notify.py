import json
from unittest.mock import patch

from kraken.server import consts, initdb
from kraken.server.models import db, Project, Branch, Flow, Secret, Stage, AgentsGroup, Agent, Tool
from kraken.server.models import Run, Step, System, Job, RepoChanges

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
