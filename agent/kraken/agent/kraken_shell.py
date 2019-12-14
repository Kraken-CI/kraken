from . import utils

def run(step, **kwargs):  # pylint: disable=unused-argument
    cmd = step['cmd']
    cwd = step.get('cwd', None)
    ret, out = utils.execute(cmd, cwd=cwd)
    if ret != 0:
        return out, 'cmd exited with non-zero retcode'
    return 0, ''
