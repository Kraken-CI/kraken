def stage(ctx):
    return {
        "parent": "Build",
        "triggers": {
            "manual": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "publish",
            "timeout": 600,
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
                "tool": "git",
                "checkout": "github.com/Kraken-CI/helm-repo.git",
                "access-token": "github_token",
                "branch": "gh-pages"
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=0.#{KK_FLOW_SEQ} helm_dest=./helm-repo/charts helm_release",
                "cwd": "kraken",
                "timeout": 120
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=0.#{KK_FLOW_SEQ} github_release",
                "cwd": "kraken",
                "env": {
                    "GITHUB_TOKEN": "#{KK_SECRET_SIMPLE_github_token}"
                },
                "timeout": 300
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
            	"agents_group": "all",
                "config": "default"
            }]
        }]
    }
