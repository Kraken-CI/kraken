import json
import logging

from . import utils
from . import tool

log = logging.getLogger(__name__)


def run_tests(step, report_result=None):
    cwd = step.get('cwd', '.')
    not_match_f = step.get('not-match-f', None)
    exclude_dir = step.get('exclude-dir', None)

    cmd = 'cloc . --json'
    if not_match_f:
        cmd += " --not-match-f '%s'" % not_match_f
    if exclude_dir:
        cmd += " --exclude-dir '%s'" % exclude_dir

    ret, out = utils.execute(cmd, cwd=cwd, out_prefix='')
    if ret != 0:
        log.error('cloc exited with non-zero retcode: %s', ret)
        return ret, 'cloc exited with non-zero retcode'

    data = json.loads(out)
    for f, v in data.items():
        if f == 'header':
            continue
        else:
            test = f
        values = dict(blank=dict(value=v['blank'], iterations=1),
                      comment=dict(value=v['comment'], iterations=1),
                      code=dict(value=v['code'], iterations=1),
                      total=dict(value=v['blank'] + v['comment'] + v['code'], iterations=1),
                      files=dict(value=v['nFiles'], iterations=1))
        result = dict(cmd='', status=1, test=test, values=values)
        report_result(result)

    return 0, ''


if __name__ == '__main__':
    tool.main()
