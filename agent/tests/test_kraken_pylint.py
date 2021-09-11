import json
from unittest.mock import patch

import pytest

from kraken.agent import kraken_pylint


@pytest.mark.parametrize("git_url", [
    'git@github.com:Kraken-CI/kraken.git',
    'https://github.com/Kraken-CI/kraken.git',
    'https://github.com/Kraken-CI/kraken'
])
def test__get_git_url(git_url):
    values = [
        (0, git_url),
        (0, '''  origin/HEAD -> origin/master
  origin/master''')
    ]
    with patch('kraken.agent.utils.execute', side_effect=values):
        result = kraken_pylint._get_git_url('/tmp')
        assert result == 'https://github.com/Kraken-CI/kraken/blob/master'


def test_run_analysis():
    rcvd_issues = []
    def _rep_issue(issue):
        rcvd_issues.append(issue)

    step = {
        'rcfile': 'pylint.rc',
        'modules_or_packages': '.'
    }

    issues = [{
        "path": "path",
        "line": 123,
        "message": "msg",
    }]
    issues_json = json.dumps(issues)

    with patch('kraken.agent.utils.execute', return_value=(0, issues_json)) as ue, \
         patch('kraken.agent.kraken_pylint._get_git_url', return_value='https://github.com/Kraken-CI/kraken/blob/master'):
        ret, msg = kraken_pylint.run_analysis(step, report_issue=_rep_issue)

        ue.assert_called_once()
        print('ARGS', ue.call_args)
        assert ue.call_args.kwargs['cwd'] == '.'
        assert ue.call_args.kwargs['timeout'] == 180
        assert 'pylint' in ue.call_args.args[0]
        assert '--exit-zero' in ue.call_args.args[0]
        assert '--rcfile=pylint.rc' in ue.call_args.args[0]
        assert '-f json' in ue.call_args.args[0]

    assert ret == 0
    assert msg == ''
    assert rcvd_issues[0] == {'line': 123,
                              'message': 'msg',
                              'path': 'path',
                              'url': 'https://github.com/Kraken-CI/kraken/blob/master/path#L123'}
