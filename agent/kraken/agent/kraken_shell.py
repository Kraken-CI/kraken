from . import utils

def run(step, **kwargs):  # pylint: disable=unused-argument
    cmd = step['cmd']
    cwd = step.get('cwd', None)
    timeout = int(step.get('timeout', 60))
    ret, out = utils.execute(cmd, cwd=cwd, timeout=timeout)
    if ret != 0:
        return ret, 'cmd exited with non-zero retcode: %s' % ret
    return 0, ''
