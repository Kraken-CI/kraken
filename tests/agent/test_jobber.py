import sys
from unittest.mock import patch
sys.path.append('kraken/agent')

import jobber
import config


def test__load_tools_list_1():
    with patch('config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert result == set()


def test__load_tools_list_2():
    with patch('config.get', return_value='/'):
        result = jobber._load_tools_list()
        assert result == set()
