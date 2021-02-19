# Copyright 2020 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import json

import jsonschema

# pylint: disable=line-too-long

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
    "run_label": "a.#{KK_CI_DEV_RUN_SEQ}",
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
        "repo": {
            "url": "https://github.com/Kraken-CI/kraken.git",
            "branch": "master",
            "interval": "20m"
        }
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
        "repo": {
            "repos": [{
                "url": "https://github.com/Kraken-CI/kraken",
                "branch": "master"
            }, {
                "url": "https://github.com/Kraken-CI/workflow-examples",
                "branch": "master"
            }],
            "interval": "20m"
        }
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
    "title": "Schema of Kraken Workflow Schema",
    "description": "This is a schema that defines format of Kraken Workflow Schema.",

    "type": "object",
    "additionalProperties": False,
    "properties": {
        "parent": {
            "description": "A name of the parent stage. `'root'` if there is no parent. This allows chaining stages.",
            "type": "string"
        },
        "triggers": {
            "description": "One or more triggers that cause starting a new run of this stage.",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "parent": {
                    "description": "A parent stage to current one or 'root'. It allows defining a chain of stages.",
                    "type": "boolean"
                },
                "interval": {
                    "type": "string"
                },
                "date": {
                    "type": "string"
                },
                "cron": {
                    "description": "A parent stage to current one or 'root'. It allows defining a chain of stages.",
                    "type": "string"
                },
                "repo": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "url": {
                            "type": "string"
                        },
                        "branch": {
                            "type": "string"
                        },
                        "repos": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "url": {
                                    "type": "string"
                                },
                                "branch": {
                                    "type": "string"
                                }
                            }
                        },
                        "interval": {
                            "oneOf": [{
                                "type": "integer",
                                "minimum": 1
                            }, {
                                "type": "string"
                            }]
                        }
                    }
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
            "description": "A custom label format for flows.",
            "type": "string"
        },
        "run_label": {
            "description": "A custom label format for runs.",
            "type": "string"
        },
        "jobs": {
            "description": "A list of jobs that are executed in the run. Jobs are executed in parallel.",
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {
                        "description": "A name of the job.",
                        "type": "string"
                    },
                    "timeout": {
                        "description": "An initial timeout of the job. If there are more than 10 historical succeded jobs then timeout is estimated automatically.",
                        "type": "integer",
                        "minimum": 30
                    },
                    "steps": {
                        "description": "An array of steps that are executed by an agent. Each step has indicated tool that is executing it. Steps are executed in given order.",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "oneOf": [{
                                "if": { "properties": { "tool": { "const": "shell" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "required": ["tool", "cmd"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool that executes provided command in a shell.",
                                            "const": "shell"
                                        },
                                        "cmd": {
                                            "description": "A command to execute.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "user": {
                                            "description": "A user that is used to execute a command.",
                                            "default": "kraken",
                                            "type": "string"
                                        },
                                        "env": {
                                            "description": "A dictionary with environment variables and their values.",
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "string"
                                            }
                                        },
                                        "timeout": {
                                            "description": "A timeout in seconds that limits time of step execution. It is guareded by an agent. If it is exceeded then the step is arbitrarly terminated.",
                                            "type": "integer",
                                            "minimum": 30
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                    "required": ["tool", "checkout"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool for cloning Git repository.",
                                            "const": "git"
                                        },
                                        "checkout": {
                                            "description": "An URL to the repository.",
                                            "type": "string"
                                        },
                                        "branch": {
                                            "description": "A branch to checkout.",
                                            "default": "master",
                                            "type": "string"
                                        },
                                        "destination": {
                                            "description": "A destination folder for the repository. Default is empty ie. the name of the repository.",
                                            "type": "string"
                                        },
                                        "ssh-key": {
                                            "description": "A name of a secret that holds SSH username and key.",
                                            "type": "string"
                                        },
                                        "access-token": {
                                            "description": "An access token for GitLab use case.",
                                            "type": "string"
                                        },
                                        "timeout": {
                                            "description": "A timeout in seconds that limits time of step execution. It is guareded by an agent. If it is exceeded then the step is arbitrarly terminated.",
                                            "type": "integer",
                                            "minimum": 30
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "artifacts" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "required": ["tool", "source"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool for storing and retrieving artifacts in Kraken global storage.",
                                            "const": "artifacts"
                                        },
                                        "action": {
                                            "description": "An action that artifacts tool should execute. Default is `upload`.",
                                            "type": "string",
                                            "enum": ["download", "upload"]
                                        },
                                        "source": {
                                            "description": "A path or list of paths that should be archived or retreived. A path can indicate a folder or a file. A path, in case of upload action, can contain globbing signs `*` or `**`. A path can be relative or absolute.",
                                            "oneOf": [{
                                                "description": "A single path.",
                                                "type": "string"
                                            }, {
                                                "description": "A list of paths.",
                                                "type": "array",
                                                "items": {
                                                    "type": "string"
                                                }
                                            }]
                                        },
                                        "destination": {
                                            "description": "A path were the artifact(s) should be stored. In case of download action, if the destination folder does not exist then it is created.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "public": {
                                            "description": "Determines if artifacts should be public and available to users in web UI (`True`) or if they should be only accessible internally to other stages but only in the same flow (`False`).",
                                            "default": False,
                                            "type": "boolean"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                    "required": ["tool", "action"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool for storing and restoring files from cache.",
                                            "const": "cache"
                                        },
                                        "action": {
                                            "description": "An action that the tool should perform.",
                                            "type": "string",
                                            "enum": ["save", "restore"]
                                        },
                                        "key": {
                                            "description": "A key under which files are stored in or restored from cache.",
                                            "type": "string"
                                        },
                                        "keys": {
                                            "description": "A list of key under which files are restored from cache.",
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "paths": {
                                            "description": "Source paths used in `store` action.",
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "expiry": {
                                            "description": "Not implemented yet.",
                                            "type": "string"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                    "required": ["tool", "rcfile", "modules_or_packages"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool that allows for static analysis of Python source code.",
                                            "const": "pylint"
                                        },
                                        "pylint_exe": {
                                            "description": "An alternative path or command to pylint.",
                                            "default": "pylint",
                                            "type": "string"
                                        },
                                        "rcfile": {
                                            "description": "A path to pylint rcfile.",
                                            "type": "string"
                                        },
                                        "modules_or_packages": {
                                            "description": "A path or paths to Python modules or packages that should be checked.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                            "description": "A tool that allows for running Python tests.",
                                            "const": "pytest"
                                        },
                                        "pytest_exe": {
                                            "description": "An alternative path or command to pytest.",
                                            "default": "pytest-3",
                                            "type": "string"
                                        },
                                        "params": {
                                            "description": "Parameters passed directly to pytest executable.",
                                            "type": "string"
                                        },
                                        "pythonpath": {
                                            "description": "Extra paths that are used by Python to look for modules/packages that it wants to load.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
                                        }
                                    }
                                },
                                "else": {
                                    "additionalProperties": False,
                                    "properties": {
                                    }
                                }
                            }, {
                                "if": { "properties": { "tool": { "const": "junit_collect" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "required": ["tool", "file_glob"],
                                    "properties": {
                                        "tool": {
                                            "description": "A tool that allows for collecting test results stored in JUnit files.",
                                            "const": "junit_collect"
                                        },
                                        "file_glob": {
                                            "description": "A glob pattern for searching test result files.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
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
                                "if": { "properties": { "tool": { "const": "gotest" } } },
                                "then": {
                                    "additionalProperties": False,
                                    "properties": {
                                        "tool": {
                                            "description": "A tool that allows for running Go language tests.",
                                            "const": "gotest"
                                        },
                                        "go_exe": {
                                            "description": "An alternative path or command to `go`.",
                                            "type": "string"
                                        },
                                        "params": {
                                            "description": "Parameters passed directly to `go test`.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "timeout": {
                                            "description": "A timeout in seconds that limits time of step execution. It is guareded by an agent. If it is exceeded then the step is arbitrarly terminated.",
                                            "type": "integer",
                                            "minimum": 30
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                            "description": "A tool that allows for running Angular `ng lint`, that is performing static analysis of TypeScript in Angular projects.",
                                            "const": "nglint"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                            "description": "A tool that allows for running counting lines of code.",
                                            "const": "cloc"
                                        },
                                        "not-match-f": {
                                            "description": "Filter out files that match to provided regex.",
                                            "type": "string"
                                        },
                                        "exclude-dir": {
                                            "description": "Excluded provided list of directories.",
                                            "type": "string"
                                        },
                                        "cwd": {
                                            "description": "A current working directory where the step is executed.",
                                            "default": ".",
                                            "type": "string"
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                                            "description": "A tool that allows for generating random test case results.",
                                            "const": "rndtest"
                                        },
                                        "count": {
                                            "description": "A number of expected test cases.",
                                            "oneOf": [{
                                                "type": "integer",
                                                "minimum": 1
                                            }, {
                                                "type": "string"
                                            }]
                                        },
                                        "attempts": {
                                            "description": "A number of times the step is retried if if it returns error.",
                                            "default": 1,
                                            "type": "integer"
                                        },
                                        "sleep_time_after_attempt": {
                                            "description": "A sleep time between subsequent execution attempts.",
                                            "default": 0,
                                            "type": "integer"
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
                        "description": "It defines the surroundings of a job execution.",
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["system", "agents_group"],
                            "properties": {
                                "agents_group": {
                                    "description": "A name of agents group. An agent from this group will be used to execute the job. There is a special built-in group, `'all'` that gathers all agents.",
                                    "type": "string"
                                },
                                "executor": {
                                    "description": "An executor that agent is using to execute a job.",
                                    "enum": ["local", "docker", "lxd"],
                                    "default": "local",
                                    "type": "string"
                                },
                                "system": {
                                    "description": "An operating system name or list of such names that should be used for job execution. If this is a list then the number of job instances is multiplied by numer of systems - each instance has its system. There is a special system name, `'any'`, that ignores system selection by jobs scheduler.",
                                    "oneOf": [{
                                        "type": "string"
                                    }, {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        }
                                    }]
                                },
                                "config": {
                                    "description": "Not implemented yet.",
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }
        },
        "notification": {
            "description": "Notification allows for configuring a notification means that are used to pass an information about stage's run result. There are several communication methods supported.",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "email":  {
                    "description": "It sends run results to indicated email address.",
                    "type": "string"
                },
                "slack": {
                    "description": "It sends run results to indicated Slack channel.",
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "channel": {
                            "description": "Selected Slack channel",
                            "type": "string"
                        }
                    }
                },
                "github": {
                    "description": "It sends run results to associated pull request page on GitHub.",
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "credentials": {
                            "description": "Credentials (user:password) that allows access to the project on GitHub.",
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


def dump_to_json():
    with open('kraken.schema.json', 'w') as fp:
        json.dump(schema, fp)


if __name__ == '__main__':
    if sys.argv[1] == 'test':
        test()
    elif sys.argv[1] == 'json':
        dump_to_json()
