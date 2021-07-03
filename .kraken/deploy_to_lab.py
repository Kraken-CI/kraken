def stage(ctx):
    return {
        "parent": "Build",
        "triggers": {
            "manual": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "deploy to lab",
            "steps": [{
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "artifacts",
                "action": "download",
                "public": True,
                "source": "kraken-docker-compose-0.#{KK_FLOW_SEQ}.yaml",
                "cwd": "kraken"
            }, {
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends python3-setuptools python3-wheel python3-pip python3-venv",
                "timeout": 300
            }, {
                "tool": "shell",
                "cmd": 'printf "$labenv" > lab.env',
                "cwd": "kraken",
                "env": {
                    "labenv": "#{KK_SECRET_SIMPLE_labenv}"
                }
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=0.#{KK_FLOW_SEQ} deploy_lab",
                "cwd": "kraken",
                "env": {
                    "host": "#{KK_SECRET_SIMPLE_deploy_host}"
                }
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
                "agents_group": "external",
                "config": "default"
            }]
        }]
    }
