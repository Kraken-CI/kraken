def stage(ctx):
    kk_ver = "#{env.KK_BASE_VER}.#{KK_FLOW_SEQ}"

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
                "source": "kraken-docker-compose-%s.yaml" % kk_ver,
                "cwd": "kraken"
            }, {
                "tool": "shell",
                "cmd": 'printf "$labenv" > lab.env',
                "cwd": "kraken",
                "env": {
                    "labenv": "#{KK_SECRET_SIMPLE_labenv}"
                }
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=%s deploy_lab" % kk_ver,
                "cwd": "kraken",
                "env": {
                    "host": "#{KK_SECRET_SIMPLE_deploy_host}"
                },
                "timeout": 1000
            }],
            "environments": [{
                "system": "krakenci/bld-kraken-22.04:20231112",
                "executor": "docker",
                "agents_group": "external",
                "config": "default"
            }]
        }]
    }
