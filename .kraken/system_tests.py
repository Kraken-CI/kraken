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
            "timeout": 600,
            "steps": [{
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "shell",
                "cmd": "rake run_systests",
                "cwd": "kraken",
                "timeout": 800
            }],
            "environments": [{
                "system": "krakenci/bld-kraken",
                "executor": "docker",
            	"agents_group": "all",
                "config": "default"
            }]
        }]
    }
