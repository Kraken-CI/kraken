import json
from unittest.mock import patch, MagicMock

import pytest

from kraken.server import notify, consts

class SecretStub:
    pass

def test_notify_github_start():
    run = MagicMock()
    run.stage.name = 'stag'
    run.label = 'lbl'
    run.stage.schema = {
        'notification': {
            'github': {
                'credentials': '#{KK_SECRET_SIMPLE_gh_creds}',
            }
        }
    }
    run.flow.trigger_data = {
        'after': 'sha1',
        'repo': 'http://gh.com/Kraken-CI/kraken.git',
    }
    s = SecretStub()
    s.deleted = False
    s.kind = consts.SECRET_KIND_SIMPLE
    s.name = 'gh_creds'
    s.data = {'secret': 'user:token'}
    run.stage.branch.project.secrets = [s]

    with patch('requests.post') as rp, patch('kraken.server.notify._get_srv_url', return_value='http://aa.pl'):
        notify.notify(run, 'start')
        rp.assert_called_once()
        assert rp.call_args[0][0] == 'https://api.github.com/repos/Kraken-CI/kraken/statuses/sha1'
        assert rp.call_args[1]['auth'] == ['user', 'token']
        assert 'data' in rp.call_args[1]
        data = rp.call_args[1]['data']
        data = json.loads(data)
        assert data['state'] == 'pending'
        assert data['context'] == 'kraken / stag [lbl]'
        assert data['target_url'] == 'http://aa.pl/runs/1'
        assert data['description'] == 'waiting for results'


def test_notify_github_end():
    run = MagicMock()
    run.stage.name = 'stag'
    run.label = 'lbl'
    run.regr_cnt = 1
    run.fix_cnt = 2
    run.issues_new = 3
    run.stage.schema = {
        'notification': {
            'github': {
                'credentials': 'user:token',
            }
        }
    }
    run.flow.trigger_data = {
        'after': 'sha1',
        'repo': 'http://gh.com/Kraken-CI/kraken.git',
    }

    with patch('requests.post') as rp, patch('kraken.server.notify._get_srv_url', return_value='http://aa.pl'):
        notify.notify(run, 'end')
        rp.assert_called_once()
        assert rp.call_args[0][0] == 'https://api.github.com/repos/Kraken-CI/kraken/statuses/sha1'
        assert rp.call_args[1]['auth'] == ['user', 'token']
        assert 'data' in rp.call_args[1]
        data = rp.call_args[1]['data']
        data = json.loads(data)
        assert data['state'] == 'failure'
        assert data['context'] == 'kraken / stag [lbl]'
        assert data['target_url'] == 'http://aa.pl/runs/1'
        assert data['description'] == 'regressions: 1, fixes: 2, new issues: 3'
