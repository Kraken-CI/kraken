import sys
from unittest.mock import patch

from kraken.agent import jobber


def test__load_tools_list_1():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert type(result) == dict


def test__load_tools_list_2():
    with patch('kraken.agent.config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert type(result) == dict
