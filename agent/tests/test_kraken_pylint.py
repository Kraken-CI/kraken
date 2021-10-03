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

    call_args = []
    def my_exe(*args, **kwargs):
        call_args.extend((args, kwargs))
        cmd = args[0]
        f = cmd.split()[-1][:-1]
        with open(f, 'w') as fh:
            fh.write(issues_json)
        return 0, ''

    with patch('kraken.agent.utils.execute', my_exe), \
         patch('kraken.agent.kraken_pylint._get_git_url', return_value='https://github.com/Kraken-CI/kraken/blob/master'):
        ret, msg = kraken_pylint.run_analysis(step, report_issue=_rep_issue)

        assert call_args
        print('ARGS', call_args)
        assert call_args[1]['cwd'] == '.'
        assert call_args[1]['timeout'] == 180
        assert 'pylint' in call_args[0][0]
        assert '--exit-zero' in call_args[0][0]
        assert '--rcfile=pylint.rc' in call_args[0][0]
        assert '-f json' in call_args[0][0]

    assert ret == 0
    assert msg == ''
    assert rcvd_issues[0] == {'line': 123,
                              'message': 'msg',
                              'path': 'path',
                              'url': 'https://github.com/Kraken-CI/kraken/blob/master/path#L123'}
