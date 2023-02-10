# Copyright 2023 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from unittest.mock import patch

import pytest
from hamcrest import assert_that, has_entries, matches_regexp, contains_exactly, instance_of

from common import check_missing_tests_in_mod

from kraken.server import logs


# TODO
#def test_missing_tests():
#    check_missing_tests_in_mod(logs, __name__)


def test_MaskingLogRecord():
    #mlr = logs.MaskingLogRecord(name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None)
    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg', [], 'exc_info')#, func=None, sinfo=None)
    msg = mlr.getMessage()
    assert msg == 'msg'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg qwert asdfg zxcb', [], 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'start')
    msg = mlr.getMessage()
    assert msg == '******ert asdfg zxcb'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg qwert asdfg zxcb', [], 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'end')
    msg = mlr.getMessage()
    assert msg == 'msg qwert asdf******'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg qwert secret zxcb', [], 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'middle')
    msg = mlr.getMessage()
    assert msg == 'msg qwert ****** zxcb'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg %s %d', ('qwe', 1), 'exc_info')#, func=None, sinfo=None)
    msg = mlr.getMessage()
    assert msg == 'msg qwe 1'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', '%s msg %d', ('secret', 1), 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'start')
    msg = mlr.getMessage()
    assert msg == '****** msg 1'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg %d %s', (1, 'secret'), 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'end')
    msg = mlr.getMessage()
    assert msg == 'msg 1 ******'

    mlr = logs.MaskingLogRecord('name', 'level', 'pathname', 'lineno', 'msg %s %d', ('secret', 1), 'exc_info')#, func=None, sinfo=None)
    mlr.add_mask_secret('secret', 'middle')
    msg = mlr.getMessage()
    assert msg == 'msg ****** 1'
