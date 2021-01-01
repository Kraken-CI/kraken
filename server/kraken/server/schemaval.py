import jsonschema

data1 = {
    "parent": "Tarball",
    "triggers": {
        "parent": True
    },
    "parameters": [],
    "configs": [],
    "jobs": [
        {
            "name": "build",
            "timeout": 5000,
            "steps": [
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "echo \"${GOOGLE_KEY}\" | docker login -u _json_key --password-stdin https://eu.gcr.io",
                    "env": {
                        "GOOGLE_KEY": "#{KK_SECRET_SIMPLE_google_key}"
                    }
                },
                {
                    "tool": "shell",
                    "cmd": "rake build_all",
                    "cwd": "kraken",
                    "timeout": 600,
                    "env": {
                        "kk_ver": "0.#{KK_FLOW_SEQ}"
                    }
                },
                {
                    "tool": "shell",
                    "cmd": "rake publish_docker",
                    "cwd": "kraken",
                    "timeout": 1500,
                    "env": {
                        "kk_ver": "0.#{KK_FLOW_SEQ}"
                    }
                },
                {
                    "tool": "artifacts",
                    "source": [
                        "kraken-docker-compose-*.yaml",
                        ".env"
                    ],
                    "cwd": "kraken",
                    "public": True
                }
            ],
            "environments": [
                {
                    "system": "krakenci/bld-kraken",
                    "executor": "docker",
                    "agents_group": "all",
                    "config": "c1"
                }
            ]
        }
    ],
    "notification": {
        "slack": {
            "channel": "kk-results"
        },
        "email": "godfryd@gmail.com",
        "github": {
            "credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"
        }
    }
}

data2 = {
    "parent": "Build",
    "triggers": {
        "manual": True
    },
    "parameters": [],
    "configs": [],
    "jobs": [
        {
            "name": "publish on github",
            "steps": [
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "public": True,
                    "source": "kraken-docker-compose-0.#{KK_FLOW_SEQ}.yaml",
                    "cwd": "kraken"
                },
                {
                    "tool": "shell",
                    "cmd": "rake kk_ver=0.#{KK_FLOW_SEQ} github_release",
                    "cwd": "kraken",
                    "env": {
                        "GITHUB_TOKEN": "#{KK_SECRET_SIMPLE_github_token}"
                    }
                }
            ],
            "environments": [
                {
                    "system": "krakenci/bld-kraken",
                    "executor": "docker",
                    "agents_group": "all",
                    "config": "default"
                }
            ]
        }
    ]
}

data3 = {
    "parent": "Tarball",
    "triggers": {
        "parent": True
    },
    "parameters": [],
    "configs": [],
    "jobs": [
        {
            "name": "pylint agent",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends python3-setuptools",
                    "timeout": 300
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install pylint"
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install -r requirements.txt",
                    "cwd": "kraken/agent"
                },
                {
                    "tool": "shell",
                    "cmd": "cp server/kraken/server/logs.py server/kraken/server/consts.py agent/kraken/agent",
                    "cwd": "kraken"
                },
                {
                    "tool": "pylint",
                    "rcfile": "pylint.rc",
                    "modules_or_packages": "agent/kraken/agent",
                    "cwd": "kraken"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "c1"
                }
            ]
        },
        {
            "name": "pylint server",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends python3-setuptools",
                    "timeout": 300
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install poetry"
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "echo 'version = \"0.0\"' > version.py",
                    "cwd": "kraken/server/kraken"
                },
                {
                    "tool": "shell",
                    "cmd": "poetry install -n --no-root",
                    "cwd": "kraken/server",
                    "timeout": 300
                },
                {
                    "tool": "shell",
                    "cmd": "pwd && ls -al",
                    "cwd": "kraken/server"
                },
                {
                    "tool": "pylint",
                    "pylint_exe": "poetry run pylint",
                    "rcfile": "../pylint.rc",
                    "modules_or_packages": "kraken/server",
                    "cwd": "kraken/server"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "c1"
                }
            ]
        },
        {
            "name": "ng lint",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends git nodejs npm || ps axf",
                    "timeout": 300
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "npm install",
                    "cwd": "kraken/ui",
                    "timeout": 240
                },
                {
                    "tool": "nglint",
                    "cwd": "kraken/ui"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "c1"
                }
            ]
        },
        {
            "name": "cloc",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo apt-get install -y --no-install-recommends cloc || ps axf",
                    "timeout": 300
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "cloc",
                    "not-match-f": "(package-lock.json|pylint.rc)",
                    "exclude-dir": "docker-elk",
                    "cwd": "kraken"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "c1"
                }
            ]
        }
    ],
    "notification": {
        "slack": {
            "channel": "kk-results"
        },
        "email": "godfryd@gmail.com",
        "github": {
            "credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"
        }
    }
}

data4 = {
    "parent": "root",
    "triggers": {
        "parent": True
    },
    "parameters": [],
    "configs": [],
    "flow_label": "0.#{KK_FLOW_SEQ}",
    "jobs": [
        {
            "name": "tarball",
            "steps": [
                {
                    "tool": "git",
                    "checkout": "https://github.com/Kraken-CI/kraken.git",
                    "branch": "master"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zcvf kraken.tar.gz kraken"
                },
                {
                    "tool": "artifacts",
                    "source": "kraken.tar.gz"
                }
            ],
            "environments": [
                {
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }
            ]
        }
    ],
    "notification": {
        "slack": {
            "channel": "kk-results"
        },
        "email": "godfryd@gmail.com"
    }
}

data5 = {
    "parent": "Tarball",
    "triggers": {
        "parent": True
    },
    "parameters": [],
    "configs": [],
    "jobs": [
        {
            "name": "pytest agent",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo apt-get install -y python3-pip || ps axf",
                    "timeout": 300
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install pytest"
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install -r requirements.txt",
                    "cwd": "kraken/agent"
                },
                {
                    "tool": "shell",
                    "cmd": "cp consts.py logs.py ../../../agent/kraken/agent",
                    "cwd": "kraken/server/kraken/server"
                },
                {
                    "tool": "pytest",
                    "params": "-vv",
                    "cwd": "kraken/agent"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "default"
                }
            ]
        },
        {
            "name": "pytest server",
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sudo apt update && sudo apt-get install -y python3-pip || ps axf",
                    "timeout": 300
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install pytest"
                },
                {
                    "tool": "artifacts",
                    "action": "download",
                    "source": "kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "tar -zxf kraken.tar.gz"
                },
                {
                    "tool": "shell",
                    "cmd": "sudo pip3 install poetry"
                },
                {
                    "tool": "shell",
                    "cmd": "poetry install",
                    "cwd": "kraken/server"
                },
                {
                    "tool": "pytest",
                    "params": "-vv",
                    "cwd": "kraken/server"
                }
            ],
            "environments": [
                {
                    "system": "krakenci/ubuntu:20.04",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "default"
                }
            ]
        }
    ],
    "notification": {
        "slack": {
            "channel": "kk-results"
        },
        "email": "godfryd@gmail.com",
        "github": {
            "credentials": "#{KK_SECRET_SIMPLE_gh_status_creds}"
        }
    }
}

data6 = {
    "parent": "Unit Tests",
    "triggers": {
        "parent": True,
        "cron": "1 * * * *",
        "interval": "10m",
        "repository": True,
        "webhook": True
    },
    "parameters": [],
    "configs": [
        {
            "name": "c1",
            "p1": "1",
            "p2": "3"
        },
        {
            "name": "c2",
            "n3": "33",
            "t2": "asdf"
        }
    ],
    "jobs": [
        {
            "name": "make dist",
            "steps": [
                {
                    "tool": "git",
                    "checkout": "https://github.com/frankhjung/python-helloworld.git",
                    "branch": "master"
                },
                {
                    "tool": "pytest",
                    "params": "tests/testhelloworld.py",
                    "cwd": "python-helloworld"
                }
            ],
            "environments": [
                {
                    "system": "all",
                    "agents_group": "all",
                    "config": "c1"
                }
            ]
        }
    ]
}

data7 = {
    "parent": "root",
    "triggers": {
        "parent": True
    },
    "parameters": [],
    "configs": [],
    "jobs": [
        {
            "name": "timeout",
            "timeout": 30,
            "steps": [
                {
                    "tool": "shell",
                    "cmd": "sleep 1000"
                }
            ],
            "environments": [
                {
                    "system": "centos-7",
                    "agents_group": "all",
                    "config": "default"
                }
            ]
        }
    ]
}

data8 = {
    "parent": "root",
    "triggers": {
        "parent": True
    },
    "parameters": [
        {
            "name": "COUNT",
            "type": "string",
            "default": "10",
            "description": "Number of tests to generate"
        }
    ],
    "jobs": [
        {
            "name": "random tests",
            "timeout": 100000,
            "steps": [
                {
                    "tool": "rndtest",
                    "count": "#{COUNT}"
                }
            ],
            "environments": [
                {
                    "system": "ubuntu:19.10",
                    "agents_group": "docker",
                    "executor": "docker",
                    "config": "default"
                }
            ]
        }
    ],
    "notification": {
        "slack": {
            "channel": "kk-results"
        },
        "email": "godfryd@gmail.com"
    }
}

schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://example.com/product.schema.json",
    "title": "Schema of Kraken Workflow Schema",
    "description": "This is a schema that defines format of Kraken Workflow Schema.",

    "type": "object",
    "additionalProperties": False,
    "properties": {
        "parent": {
            "description": "aaa",
            "type": "string"
        },
        "triggers": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "parent": {
                    "type": "boolean"
                },
                "cron": {
                    "type": "string"
                },
                "interval": {
                    "type": "string"
                },
                "repository":{
                    "type": "boolean"
                },
                "webhook": {
                    "type": "boolean"
                },
                "manual": {
                    "type": "boolean"
                }
            }
        },
        "parameters": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "type": {
                        "type": "string"
                    },
                    "default": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    }
                }
            }
        },
        "configs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {
                    "type": "string"
                }
            }
        },
        "flow_label": {
            "type": "string"
        },
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "timeout": {
                        "type": "integer",
                        "minimum": 30
                    },
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "oneOf": [{
                                "if": { "properties": { "tool": { "const": "artifacts" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "artifacts"
                                        },
                                        "action": {
                                            "type": "string",
                                            "enum": ["download", "upload"]
                                        },
                                        "source": {
                                            "oneOf": [{
                                                "type": "string"
                                            }, {
                                                "type": "array",
                                                "items": {
                                                    "type": "string"
                                                }
                                            }]
                                        },
                                        "cwd": {
                                            "type": "string"
                                        },
                                        "public": {
                                            "type": "boolean"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "shell" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "shell"
                                        },
                                        "cwd": {
                                            "type": "string"
                                        },
                                        "timeout": {
                                            "type": "integer",
                                            "minimum": 30
                                        },
                                        "cmd": {
                                            "type": "string"
                                        },
                                        "env": {
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "string"
                                            }
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "pylint" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "pylint"
                                        },
                                        "pylint_exe": {
                                            "type": "string"
                                        },
                                        "rcfile": {
                                            "type": "string"
                                        },
                                        "modules_or_packages": {
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "nglint" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "nglint"
                                        },
                                        "cwd": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "cloc" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "cloc"
                                        },
                                        "not-match-f": {
                                            "type": "string"
                                        },
                                        "exclude-dir": {
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "git" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "git"
                                        },
                                        "checkout": {
                                            "type": "string"
                                        },
                                        "branch": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "pytest" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "pytest"
                                        },
                                        "pytest_exe": {
                                            "type": "string"
                                        },
                                        "params": {
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "rndtest" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "rndtest"
                                        },
                                        "count": {
                                            "oneOf": [{
                                                "type": "integer",
                                                "minimum": 1
                                            }, {
                                                "type": "string"
                                            }]
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "cache" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "const": "cache"
                                        },
                                        "action": {
                                            "type": "string",
                                            "enum": ["save", "restore"]
                                        },
                                        "key": {
                                            "type": "string"
                                        },
                                        "keys": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "paths": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "expiry": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }

                            }]
                        }
                    },
                    "environments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "system": {
                                    "type": "string"
                                },
                                "executor": {
                                    "type": "string"
                                },
                                "agents_group": {
                                    "type": "string"
                                },
                                "config": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }
        },
        "notification": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "slack": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "channel": {
                            "type": "string"
                        }
                    }
                },
                "email":  {
                    "type": "string"
                },
                "github": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "credentials": {
                            "type": "string"
                        }
                    }
                }
            }
        }
    },
    "required": ["parent", "triggers"]
}

def validate(instance):
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.exceptions.ValidationError as ex:
        return str(ex)
    return None


def test():
    for data in [data1, data2, data3, data4, data5, data6, data7, data8]:
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.exceptions.ValidationError as ex:
            print('problems: %s' % str(ex))


if __name__ == '__main__':
    test()
