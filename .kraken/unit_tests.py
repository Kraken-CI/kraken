def stage(ctx):
    return {
        "parent": "Tarball",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pytest agent",
            "steps": [{
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y python3-pip || ps axf",
                "timeout": 300
            }, {
                "tool": "shell",
                "cmd": "sudo pip3 install pytest"
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "sudo pip3 install -r requirements.txt",
                "cwd": "kraken/agent"
            }, {
                "tool": "shell",
                "cmd": "cp consts.py logs.py ../../../agent/kraken/agent",
                "cwd": "kraken/server/kraken/server"
            }, {
                "tool": "pytest",
                "params": "-vv",
                "cwd": "kraken/agent"
            }],
            "environments": [{
                "system": "krakenci/ubuntu:20.04",
                "agents_group": "docker",
                "executor": "docker",
                "config": "default"
            }]
        }, {
            "name": "pytest server",
            "steps": [{
                "tool": "shell",
                "cmd": "docker run --name kkut -p 15432:5432 -e POSTGRES_DB=kkut -e POSTGRES_USER=kkut -e POSTGRES_PASSWORD=kkut postgres:11",
                "background": True,
                "timeout": 12400
            }, {
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y python3-pip || ps axf",
                "timeout": 300
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "sudo pip3 install poetry",
            }, {
                "tool": "shell",
                "cmd": "poetry install",
                "cwd": "kraken/server",
                "timeout": 240
            }, {
                "tool": "shell",
                "cmd": "echo 'version = \'0.0\'' > version.py",
                "cwd": "kraken/server/kraken",
            }, {
                "tool": "pytest",
                "pytest_exe": "sleep 6; POSTGRES_URL=postgresql://kkut:kkut@localhost:15432/ poetry run pytest",
                "cwd": "kraken/server"
            }],
            "environments": [{
                "system": "krakenci/ubuntu:20.04",
                "agents_group": "docker",
                "executor": "docker",
                "config": "default"
            }]
        }],
        "notification": {
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com",
            "github": {"credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"}
        }
    }
