def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "flow_label": "0.#{KK_FLOW_SEQ}",
        "jobs": [{
            "name": "tarball",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/Kraken-CI/kraken.git",
                "branch": "master"
            }, {
                "tool": "shell",
                "cmd": "tar -zcvf kraken.tar.gz kraken"
            }, {
                "tool": "artifacts",
                "source": "kraken.tar.gz"
            }],
            "environments": [{
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }],
        "notification": {
            "changes": {
                "slack": {"channel": "kk-results"},
                "email": "godfryd@gmail.com"
            }
        }
    }
