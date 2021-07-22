import os
import tempfile

import pytest

from kraken.agent import kraken_junit_collect
from kraken.agent import consts


RESULTS_1 = """<?xml version="1.0" encoding="UTF-8" ?>
   <testsuites id="20140612_170519" name="New_configuration (14/06/12 17:05:19)" tests="225" failures="1262" time="0.001">
      <testsuite id="codereview.cobol.analysisProvider" name="COBOL Code Review" tests="45" failures="17" time="0.001">
         <testcase id="codereview.cobol.rules.ProgramIdRule" name="Use a program name that matches the source file name" time="0.001">
            <failure message="PROGRAM.cbl:2 Use a program name that matches the source file name" type="WARNING">
WARNING: Use a program name that matches the source file name
Category: COBOL Code Review – Naming Conventions
File: /project/PROGRAM.cbl
Line: 2
      </failure>
    </testcase>
  </testsuite>
</testsuites>"""

STATS_1 = {
    consts.TC_RESULT_FAILED: 1,
}


RESULTS_2 = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Data Driven &amp; Gherkin &amp; Keyword Driven" tests="12" errors="0" failures="1" skipped="0" time="0.098">
<testcase classname="Data Driven &amp; Gherkin &amp; Keyword Driven.Data Driven" name="Division" time="0.005">
</testcase>
<testcase classname="Data Driven &amp; Gherkin &amp; Keyword Driven.Data Driven" name="Failing" time="0.003">
<failure message="2 != 3" type="AssertionError"/>
</testcase>
<testcase classname="Data Driven &amp; Gherkin &amp; Keyword Driven.Data Driven" name="Calculation error" time="0.007">
</testcase>
</testsuite>
"""

STATS_2 = {
    consts.TC_RESULT_PASSED: 2,
    consts.TC_RESULT_FAILED: 1,
}


RESULTS_3 = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="org.apache.lucene.index.TestSortedSetDocValues" tests="1" skipped="0" failures="0" errors="0" timestamp="2021-07-22T06:03:44" hostname="rivendel" time="0.004">
  <properties/>
  <testcase name="testNoMoreOrdsConstant" classname="org.apache.lucene.index.TestSortedSetDocValues" time="0.004"/>
  <testcase classname="org.apache.lucene.index.TestErr" name="err" time="0.003">
    <error message="2 != 3"/>
  </testcase>
  <testcase classname="org.apache.lucene.index.TestSkip" name="skip" time="0.003">
    <skipped/>
  </testcase>
  <system-out><![CDATA[]]></system-out>
  <system-err><![CDATA[]]></system-err>
</testsuite>"""

STATS_3 = {
    consts.TC_RESULT_PASSED: 1,
    consts.TC_RESULT_DISABLED: 1,
    consts.TC_RESULT_ERROR: 1,
}


TEST_RESULTS = {
    'RESULTS_1': (RESULTS_1, STATS_1),
    'RESULTS_2': (RESULTS_2, STATS_2),
    'RESULTS_3': (RESULTS_3, STATS_3),
}


@pytest.mark.parametrize("results_set", list(TEST_RESULTS.keys()))
def test_run_tests(results_set):
    rs, exp_stats = TEST_RESULTS[results_set]

    with tempfile.TemporaryDirectory() as tmpdirname:
        p = os.path.join(tmpdirname, 'out.xml')
        with open(p, 'w') as f:
            f.write(rs)

        step = dict(cwd=tmpdirname)
        print(step)

        collected_results = []
        def _report_result(res):
            collected_results.append(res)

        kraken_junit_collect.run_tests(step, report_result=_report_result)

        stats = dict()
        for res in collected_results:
            s = res['status']
            if s not in stats:
                stats[s] = 0
            stats[s] += 1

        assert stats == exp_stats
