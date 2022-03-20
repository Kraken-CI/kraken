def stage(ctx):
    return {
        "parent": "Build",
        "triggers": {
            "manual": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "systest",
            "timeout": 2000,
            "steps": [{
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "shell",
                "cmd": "rake pulumi_init",
                "cwd": "kraken",
                "timeout": 120
            }, {
                "tool": "shell",
                "cmd": "rake run_systests",
                "cwd": "kraken",
                "timeout": 1600,
                "env": {
                    "AWS_ACCESS_KEY_ID": "#{KK_SECRET_SIMPLE_aws_access_key_id}",
                    "AWS_SECRET_ACCESS_KEY": "#{KK_SECRET_SIMPLE_aws_secret_access_key}"
                },
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
            	"agents_group": "all",
                "config": "default"
            }]
        }]
    }
