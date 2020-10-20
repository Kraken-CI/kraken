def stage(ctx):
    return {
        "parent": "Tarball",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pytest",
            "steps": [{
                "tool": "shell",
                "cmd": "apt update && apt-get install -y python3-pip || ps axf",
                "timeout": 300
            }, {
                "tool": "shell",
                "cmd": "pip3 install pytest"
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "pip3 install -r requirements.txt",
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
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }],
        "notification": {
            "changes": {
                "slack": {"channel": "kk-results"},
                "email": "godfryd@gmail.com"
            }
        }
    }
