def stage(ctx):
    kk_ver = "1.2.#{KK_FLOW_SEQ}"

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
                "tool": "shell",
                "cmd": "sudo apt update && sudo apt-get install -y python3-pip",
                "timeout": 300
            }, {
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "shell",
                "cmd": "sudo pip3 install -r tests/requirements.txt",
                "cwd": "kraken",
            }, {
                "tool": "shell",
                "cmd": "rake pulumi_init",
                "cwd": "kraken",
                "timeout": 120,
                "env": {
                    "kk_ver": kk_ver,
                }
            }, {
                "tool": "shell",
                "cmd": "rake run_systests",
                "cwd": "kraken",
                "timeout": 1600,
                "env": {
                    "AWS_ACCESS_KEY_ID": "#{KK_SECRET_SIMPLE_aws_access_key_id}",
                    "AWS_SECRET_ACCESS_KEY": "#{KK_SECRET_SIMPLE_aws_secret_access_key}"
                },
            }, {
                "tool": "junit_collect",
                "cwd": "kraken",
                "file_glob": "tests/systests-results.xml"
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
            	"agents_group": "all",
                "config": "default"
            }]
        }]
    }
