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
                "cmd": "sudo apt update && sudo apt-get install -y python3-pip zsh",
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
                "pytest_exe": "pytest",
                "params": "-vv",
                "cwd": "kraken/agent"
            }],
            "environments": [{
                #"system": "krakenci/ubuntu:20.04",
                #"agents_group": "docker",
                #"executor": "docker",
                "system": "Canonical:0001-com-ubuntu-server-focal:20_04-lts:20.04.202109080",
                "agents_group": "azure-vm",
                "config": "default"
            }]
        }, {
            "name": "pytest server",
            "timeout": 1200,
            "steps": [{
                "tool": "shell",
                "cmd": "docker rm -f -v kkut; docker run --rm --name kkut -p 15432:5432 -e POSTGRES_DB=kkut -e POSTGRES_USER=kkut -e POSTGRES_PASSWORD=kkut postgres:11",
                "background": True,
                "timeout": 12400
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "rake prepare_env",
                "cwd": "kraken",
                "timeout": 300
            }, {
                "tool": "pytest",
                "pytest_exe": "POSTGRES_URL=postgresql://kkut:kkut@172.17.0.1:15432/ ../venv/bin/poetry run pytest",
                "cwd": "kraken/server"
            }],
            "environments": [{
                "system": "krakenci/bld-kraken:20221115",
                "agents_group": "docker",
                "executor": "docker",
                #"system": "ubuntu:20.04",
                #"agents_group": "aws-ecs-fg",
                "config": "default"
            }]
        }],
        "notification": {
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com",
            "github": {"credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"}
        }
    }
