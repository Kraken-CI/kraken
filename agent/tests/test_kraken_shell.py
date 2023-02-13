from kraken.agent import kraken_shell


def test_run_ls():
    step = {
        'cmd': 'ls -al',
    }

    ret, msg = kraken_shell.run(step)

    assert ret == 0
    assert msg == ''


def test_run_echo():
    step = {
        'cmd': 'echo AAA',
    }

    ret, msg, out = kraken_shell.run(step, testing=True)

    assert ret == 0
    assert msg == ''
    assert out == 'AAA\n'


def test_run_false():
    step = {
        'cmd': 'false',
    }

    ret, msg = kraken_shell.run(step)

    assert ret == 1
    assert msg == 'cmd exited with non-zero retcode: 1'


def test_run_wrong_cwd():
    step = {
        'cmd': 'true',
        'cwd': '/non/existing/dir'
    }

    ret, msg = kraken_shell.run(step)

    assert ret == 1
    assert msg == "[Errno 2] No such file or directory: '/non/existing/dir'"


def test_run_script_ok():
    step = {
        'script': 'echo AAA\necho BBB'
    }

    ret, msg, out = kraken_shell.run(step, testing=True)

    assert ret == 0
    assert msg == ''
    assert out == '+ echo AAA\nAAA\n+ echo BBB\nBBB\n'


def test_run_script_error():
    step = {
        'script': 'echo AAA\necho BBB\nfalse'
    }

    ret, msg, out = kraken_shell.run(step, testing=True)

    assert ret == 1
    assert msg == 'cmd exited with non-zero retcode: 1'
    assert out == '+ echo AAA\nAAA\n+ echo BBB\nBBB\n+ false\n'


def test_run_shell_sh():
    step = {
        'cmd': 'echo $0',
        'shell_exe': 'sh'
    }

    ret, msg, out = kraken_shell.run(step, testing=True)

    assert ret == 0
    assert msg == ''
    assert out == 'sh\n'


def test_run_shell_zsh():
    step = {
        'cmd': 'echo $0',
        'shell_exe': 'zsh'
    }

    ret, msg, out = kraken_shell.run(step, testing=True)

    assert ret == 0
    assert msg == ''
    assert out == 'zsh\n'
