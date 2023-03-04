def stage(ctx):
    kk_ver = "0.#{KK_FLOW_SEQ}"

    steps = [{
            "tool": "artifacts",
            "action": "download",
            "source": "kraken.tar.gz",
        }, {
            "tool": "shell",
            "cmd": "tar -zxf kraken.tar.gz",
        }, {
            "tool": "shell",
            "cmd": "echo \"${GOOGLE_KEY}\" | docker login -u _json_key_base64 --password-stdin https://us-docker.pkg.dev",
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
            "timeout": 1200,
            "env": {
                "kk_ver": kk_ver,
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
            "kk_ver": kk_ver,
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
                "kraken-docker-compose-%s.yaml" % kk_ver,
                ".env",
                "server/dist/krakenci_server-%s.tar.gz" % kk_ver,
                "agent/krakenci_agent-%s.tar.gz" % kk_ver,
                "client/dist/krakenci_client-%s.tar.gz" % kk_ver,
                "ui/dist/krakenci_ui-%s.tar.gz" % kk_ver,
                "clickhouse-proxy-%s.tar.gz" % kk_ver,
            ],
            "cwd": "kraken",
            "public": True
        })

    return {
        "parent": "Tarball",
        "triggers": {
            "parent": True,
        },
        "parameters": [{
            "name": "AMI",
            "type": "string",
            "default": "ami-0967f290f3533e5a8",
            "description": "AMI for Building"
        }],
        "configs": [],
        "jobs": [{
            "name": "build",
            "timeout": 5000,
            "steps": steps,
            "environments": [{
                # "system": "krakenci/bld-kraken",
                # "executor": "docker",
                # "agents_group": "all",
                "system": "#{AMI}", # my made by packer
                "agents_group": "aws-t3-micro",
                "config": "default"
            }]
        }],
        "notification": {
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com",
            "github": {"credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"}
        }
    }
