import time
import logging
from unittest.mock import patch, Mock

from kraken.agent import jobber, config


def test__load_tools_list_1():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert type(result) == dict


def test__load_tools_list_2():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert type(result) == dict


def test_run():
    config.set_config({
        'tools_dirs': '/tmp/abc/tools',
        'data_dir': '/tmp/abc/data'
    })

    step = {
        'finish': False,
        'id': 43,
        'index': 3,
        'tool': 'shell',
        'cmd': 'ls'
    }

    log = logging.getLogger(jobber.__name__)
    log.set_ctx = Mock()

    srv = Mock()
    srv.get_job_step.return_value = step

    job = {'id': 23,
           'executor': 'local',
           'deadline': time.time() + 100}

    jobber.run(srv, job)

    srv.report_step_result.assert_called_with(23,
                                              3,
                                              {'status': 'done', 'duration': 1})
