def stage(ctx):
    return {
        "parent": "Tarball",
        "trigger": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "build",
            "timeout": 5000,
            "steps": [{
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz",
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "shell",
                "cmd": "rake build_all",
                "cwd": "kraken",
                "timeout": 600,
                "env": {
                    "kk_ver": "0.#{KK_FLOW_SEQ}",
                }
            }, {
                "tool": "shell",
                "cmd": "echo \"${GOOGLE_KEY}\" | docker login -u _json_key --password-stdin https://eu.gcr.io",
                "env": {
                    "GOOGLE_KEY": "#{KK_SECRET_SIMPLE_google_key}"
                },
            }, {
                "tool": "shell",
                "cmd": "rake publish_docker",
                "cwd": "kraken",
                "timeout": 1500,
                "env": {
                    "kk_ver": "0.#{KK_FLOW_SEQ}",
                }
            }, {
                "tool": "artifacts",
                "source": [
                    "kraken-docker-compose-*.yaml",
                    ".env"
                ],
                "cwd": "kraken",
                "public": True
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
                "agents_group": "all",
                "config": "c1"
            }]
        }]
    }
