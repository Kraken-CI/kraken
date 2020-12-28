def stage(ctx):
    steps = [{
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
        # }, {
        #     "tool": "cache",
        #     "action": "restore",
        #     "key": "one-for-all"
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
        rake_cmd = "rake build_docker reuse=true"
    steps.append({
        "tool": "shell",
        "cmd": rake_cmd,
        "cwd": "kraken",
        "timeout": 1500,
        "env": {
            "kk_ver": "0.#{KK_FLOW_SEQ}",
        }
    })

    # steps.append({
    #     "tool": "cache",
    #     "action": "save",
    #     "key": "one-for-all",
    #     "paths": ["kraken/tools", "kraken/ui/node_modules"]
    # })

    if ctx.is_ci:
        steps.append({
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
        "triggers": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "build",
            "timeout": 5000,
            "steps": steps,
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
                "agents_group": "all",
                "config": "c1"
            }]
        }],
        "notification": {
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com",
            "github": {"credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"}
        }
    }
