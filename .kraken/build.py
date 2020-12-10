def stage(ctx):
    jobs = [{
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
            "cmd": "echo \"${GOOGLE_KEY}\" | docker login -u _json_key --password-stdin https://eu.gcr.io",
            "env": {
                "GOOGLE_KEY": "#{KK_SECRET_SIMPLE_google_key}"
            },
        }, {
            "tool": "shell",
            "cmd": "rake build_all",
            "cwd": "kraken",
            "timeout": 600,
            "env": {
                "kk_ver": "0.#{KK_FLOW_SEQ}",
            }
        }]

    if ctx.is_ci:
        rake_cmd = "rake publish_docker"
    else:
        rake_cmd = "rake build_docker"
    jobs.append({
        "tool": "shell",
        "cmd": rake_cmd,
        "cwd": "kraken",
        "timeout": 1500,
        "env": {
            "kk_ver": "0.#{KK_FLOW_SEQ}",
        }
    })

    if ctx.is_ci:
        jobs.append({
            "tool": "artifacts",
            "source": [
                "kraken-docker-compose-*.yaml",
                ".env"
            ],
            "cwd": "kraken",
            "public": True
        })

    return {
        "parent": "Tarball",
        "trigger": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": jobs,
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
                "agents_group": "all",
                "config": "c1"
            }]
        }]
    }
