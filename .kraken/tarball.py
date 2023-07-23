def stage(ctx):
    kk_ver = "1.4.#{KK_FLOW_SEQ}"

    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "flow_label": kk_ver,
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
            "slack": {"channel": "kk-results"},
            "email": "godfryd@gmail.com"
        }
    }
