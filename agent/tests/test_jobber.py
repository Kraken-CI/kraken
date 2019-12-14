import sys
from unittest.mock import patch

from kraken.agent import jobber
import kraken.agent.config


def test__load_tools_list_1():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert 'git' in result


def test__load_tools_list_2():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert 'git' in result
