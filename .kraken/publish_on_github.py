def stage(ctx):
    return {
        "parent": "Build",
        "triggers": {
            "manual": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "publish on github",
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
                "cmd": "rake kk_ver=0.#{KK_FLOW_SEQ} github_release",
                "cwd": "kraken",
                "env": {
                    "GITHUB_TOKEN": "#{KK_SECRET_SIMPLE_github_token}"
                }
            }],
        	"environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
            	"agents_group": "all",
            	"config": "default"
        	}]
        }]
    }
