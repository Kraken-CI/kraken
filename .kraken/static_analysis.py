def stage(ctx):
    envs = [{
        # "system": "krakenci/ubuntu:20.04",
        # "agents_group": "docker",
        # "executor": "docker",
        "system": "ami-0eb20d74951847b28", # my made by packer
        "agents_group": "aws-t2-micro",
        "config": "default"
    }]

    return {
        "parent": "Tarball",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pylint agent",
            "steps": [{
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends python3-setuptools python3-wheel python3-pip gcc python3-dev || ps axf",
                "timeout": 300
            }, {
                "tool": "shell",
                "cmd": "sudo pip3 install pylint"
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
                "cmd": "cp server/kraken/server/logs.py server/kraken/server/consts.py agent/kraken/agent",
                "cwd": "kraken"
            }, {
                "tool": "pylint",
                "rcfile": "pylint.rc",
                "modules_or_packages": "agent",
                "cwd": "kraken"
            }],
            "environments": envs
        }, {
            "name": "pylint server + client",
            "steps": [{
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends python3-setuptools python3-wheel python3-pip gcc python3-dev libpq-dev python3-venv || ps axf",
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
                "cmd": "rake prepare_env",
                "cwd": "kraken",
                "timeout": 300
            }, {
                "tool": "pylint",
                "pylint_exe": "../venv/bin/poetry run pylint",
                "rcfile": "../pylint.rc",
                "modules_or_packages": "kraken",
                "cwd": "kraken/server",
                "timeout": 300
            }, {
                "tool": "shell",
                "cmd": "rake build_client",
                "cwd": "kraken/client",
                "timeout": 300
            }, {
                "tool": "pylint",
                "pylint_exe": "../venv/bin/poetry run pylint",
                "rcfile": "../pylint.rc",
                "modules_or_packages": "kraken",
                "cwd": "kraken/client",
                "timeout": 300
            }],
            "environments": [{
                "system": "ami-0eb20d74951847b28", # my made by packer
                "agents_group": "aws-t3-micro",
                "config": "default"
            }]
        }, {
            "name": "ng lint",
            "steps": [{
                "tool": "shell",
                "cmd": "curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash - && sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends git nodejs",
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
                "cmd": "npm install",
                "cwd": "kraken/ui",
                "timeout": 400
            }, {
                "tool": "nglint",
                "cwd": "kraken/ui"
            }],
            "environments": envs
        }, {
            "name": "cloc",
            "steps": [{
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends cloc || ps axf",
                "timeout": 300
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz"
            }, {
                "tool": "cloc",
                "not-match-f": "(package-lock.json|pylint.rc)",
                "exclude-dir": "docker-elk",
                "cwd": "kraken"
            }],
            "environments": envs
        }],
        "notification": {
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com",
            "github": {"credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"}
        }
    }
