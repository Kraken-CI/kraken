# Copyright 2022 The Kraken Authors
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

import os
import tempfile

import pytest
from hamcrest import assert_that, has_entries

from kraken.agent import kraken_values_collect
from kraken.agent import consts


VALS_1 = """{
    "metric-i": 212,
    "metric-f": 2.12,
    "metric-s": "abc"
}"""

EXP_RESULT_1 = {
    'test': 'a.json',
    'cmd': '',
    'status': 1,  # passed
    'values': {
        "metric-i": {'value': 212},
        "metric-f": {'value': 2.12},
        "metric-s": {'value': "abc"}
    }
}

VALS_2 = """{
    "metric-broken
}"""

EXP_RESULT_2 = {
    'test': 'a.json',
    'cmd': '',
    'status': 3,  # error
    'values': {},
}

VALUES_SETS = {
    'VALS_1': (VALS_1, EXP_RESULT_1),
    'VALS_2': (VALS_2, EXP_RESULT_2),
}


@pytest.mark.parametrize("values_set", list(VALUES_SETS.keys()))
def test_run_tests_simple(values_set):
    vs, exp_result = VALUES_SETS[values_set]

    with tempfile.TemporaryDirectory() as tmpdirname:
        p = os.path.join(tmpdirname, 'a.json')
        with open(p, 'w') as f:
            f.write(vs)

        step = dict(cwd=tmpdirname, files=[{'name': 'a.json'}])

        collected_results = []
        def _report_result(res):
            collected_results.append(res)

        kraken_values_collect.run_tests(step, report_result=_report_result)

        res = collected_results[0]

        assert_that(res, has_entries(exp_result))


def test_run_tests_more_files():
    vals = {
        'vals1': """{
    "metric-i": 112,
    "metric-f": 1.12,
    "metric-s": "abc"
}""",
        'vals2': """{
    "metric2-i": 212,
    "metric2-f": 2.12,
    "metric2-s": "bcd"
}""",
        'vals3': """{
    "metric3-broken
}"""
    }

    with tempfile.TemporaryDirectory() as tmpdirname:
        for name, val in vals.items():
            p = os.path.join(tmpdirname, '%s.json' % name)
            with open(p, 'w') as f:
                f.write(val)

        step = dict(cwd=tmpdirname, files=[{'name': 'vals1.json'},
                                           {'name': 'vals2.json'},
                                           {'name': 'vals3.json'}])

        collected_results = []
        def _report_result(res):
            collected_results.append(res)

        kraken_values_collect.run_tests(step, report_result=_report_result)

        assert len(collected_results) == 3

        res1 = collected_results[0]
        res2 = collected_results[1]
        res3 = collected_results[2]

        assert res1 == {'cmd': '',
                        'status': 1,
                        'test': 'vals1.json',
                        'values': {'metric-f': {'value': 1.12},
                                   'metric-i': {'value': 112},
                                   'metric-s': {'value': 'abc'}}}

        assert res2 == {'cmd': '',
                        'status': 1,
                        'test': 'vals2.json',
                        'values': {'metric2-f': {'value': 2.12},
                                   'metric2-i': {'value': 212},
                                   'metric2-s': {'value': 'bcd'}}}

        assert_that(res3, has_entries({'cmd': '',
                                       'status': 3,
                                       'test': 'vals3.json',
                                       'values': {}}))
        assert res3['msg'].startswith('cannot parse')
        assert res3['msg'].endswith('/vals3.json file')
