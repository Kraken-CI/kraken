import subprocess

def run(step, **kwargs):
    cmd = step['cmd']
    ret, out = utils.execute(cmd)
    if ret != 0:
        return out, 'cmd exited with non-zero retcode'
    return 0, ''
