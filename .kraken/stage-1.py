def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True,
        },
        "flow_label": "helo-#{KK_FLOW_SEQ}",
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "hello world",
            "steps": [{
                "tool": "shell",
                "cmd": "echo 'hello world'"
            }],
            "environments": [{
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }
