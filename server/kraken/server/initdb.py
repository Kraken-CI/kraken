# Copyright 2020-2022 The Kraken Authors
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

from passlib.hash import pbkdf2_sha256

from .models import db, Branch, Stage, AgentsGroup, Setting, Tool, Project
from .models import User, BranchSequence, System
from .schema import execute_schema_code, prepare_context
from . import consts


# pylint: disable=line-too-long


INITIAL_SETTINGS = {
    'general': {
        'server_url': '',
        'minio_addr': '',
        'clickhouse_addr': '',
        'clickhouse_log_ttl': 6,
    },
    'notification': {
        'smtp_server': '',
        'smtp_tls': False,
        'smtp_from': '',
        'smtp_user': '',
        'smtp_password': None,  # password
        'slack_token': None  # password
    },
    'monitoring': {
        'sentry_dsn': None  # password
    },
    'cloud': {
        # AWS
        'aws_access_key': '',
        'aws_secret_access_key': None,  # password
        # Azure
        'azure_subscription_id': '',
        'azure_tenant_id': '',
        'azure_client_id': '',
        'azure_client_secret': None,  # password
        # Kubernetes
        'k8s_api_server_url': '',
        'k8s_namespace': 'kraken',
        'k8s_token': None,  # password
    },
    'idp': {
        # LDAP
        'ldap_enabled': False,
        'ldap_server': '',
        'bind_dn': '',
        'bind_password': None,  # password
        'base_dn': '',
        'search_filter': '',

        # Google OIDC
        'google_enabled': False,
        'google_client_id': '',
        'google_client_secret': None,  # password

        # Microsoft Azure
        'microsoft_enabled': False,
        'microsoft_client_id': '',
        'microsoft_client_secret': None,  # password

        # GitHub
        'github_enabled': False,
        'github_client_id': '',
        'github_client_secret': None,  # password

        # Auth0
        'auth0_enabled': False,
        'auth0_client_id': '',
        'auth0_client_secret': None,  # password
        'auth0_openid_config_url': '',
    }
}


def _prepare_initial_preferences():
    for group_name, group_fields in INITIAL_SETTINGS.items():
        for name, val in group_fields.items():
            s = Setting.query.filter_by(group=group_name, name=name).one_or_none()
            if s is not None:
                # correct type if necessary
                if isinstance(val, bool):
                    s.val_type = 'boolean'
                elif isinstance(val, int):
                    s.val_type = 'integer'
                elif val is None:
                    s.val_type = 'password'
                else:
                    s.val_type = 'text'
                continue

            # set value and type
            if isinstance(val, bool):
                val_type = 'boolean'
                val = str(val)
            elif isinstance(val, int):
                val_type = 'integer'
                val = str(val)
            elif val is None:
                val_type = 'password'
                val = ''
            else:
                val_type = 'text'
            Setting(group=group_name, name=name, value=val, val_type=val_type)
    db.session.commit()


def _prepare_builtin_tools():
    tool_defs = [{
        "name": "local_tool",
        "description": "A tool that allows for running arbitrary python script as a tool that is indicated by `tool_location` and `tool_entry` fields. It is possible to add arbitrary fields to step definition that will be consumed by this tool.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "additionalProperties": True,
            "required": ["tool_location", "tool_entry"],
            "properties": {
                "tool_location": {
                    "description": "A folder where a Python script is located.",
                    "type": "string"
                },
                "tool_entry": {
                    "description": "A Python script module name i.e. file name without `.py` suffix.",
                    "type": "string"
                },
            }
        }
    }, {
        "name": "git",
        "description": "A tool for cloning Git repository.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "additionalProperties": False,
            "required": ["checkout"],
            "properties": {
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
                    "description": "A name of secret that contains an access token for GitLab or GitHub.",
                    "type": "string"
                },
                "timeout": {
                    "description": "A timeout in seconds that limits time of step execution. It is guareded by an agent. If it is exceeded then the step is arbitrarly terminated.",
                    "type": "integer",
                    "minimum": 30
                },
                "git_cfg": {
                    "description": "Git config keys and values passed to -c of the clone command.",
                    "type": "object",
                    "additionalProperties": {
                        "type": "string"
                    }
                }
            }
        }
    }, {
        "name": "shell",
        "description": "A tool that executes provided command in a shell.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
                "cmd": {
                    "description": "A command to execute.",
                    "type": "string"
                },
                "script": {
                    "description": "A script code to execute.",
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
                    "minimum": 30,
                    "default": 60
                },
                "background": {
                    "description": "Indicates if step should be started and pushed to background. The step process is closed at the end of a job.",
                    "default": False,
                    "type": "boolean"
                },
                "shell_exe": {
                    "description": "An alternative path or command to shell executable (e.g.: zsh or /usr/bin/fish).",
                    "type": "string"
                },
                "ssh-key": {
                    "description": "A name of a secret that holds SSH username and key.",
                    "type": "string"
                },
            }
        }
    }, {
        "name": "pytest",
        "description": "A tool that allows for running Python tests.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
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
                }
            }
        }
    }, {
        "name": "rndtest",
        "description": "A tool that allows for generating random test case results.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
                "count": {
                    "description": "A number of expected test cases.",
                    "oneOf": [{
                        "type": "integer",
                        "minimum": 1
                    }, {
                        "type": "string"
                    }]
                },
                "override_result": {
                    "description": "A result.",
                    "oneOf": [{
                        "type": "integer",
                        "minimum": 1
                    }, {
                        "type": "string"
                    }]
                },
            }
        }
    }, {
        "name": "artifacts",
        "description": "A tool for storing and retrieving artifacts in Kraken global storage.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "required": ["source"],
            "properties": {
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
                    "description": "Determines if artifacts should be public and available to users in web UI (`True`) or if they should be only accessible internally to other stages but only in the same flow (`False`). If report_entry is set then public is True.",
                    "default": False,
                    "type": "boolean"
                },
                "report_entry": {
                    "description": "A path to HTML file that is an entry to the uploaded report. If present then it sets public to True.",
                    "type": "string"
                },
            }
        }
    }, {
        "name": "pylint",
        "description": "A tool that allows for static analysis of Python source code.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "required": ["modules_or_packages"],
            "properties": {
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
                "timeout": {
                    "description": "A timeout in seconds that limits time of step execution. It is guareded by an agent. If it is exceeded then the step is arbitrarly terminated.",
                    "type": "integer",
                    "minimum": 30
                }
            }
        }
    }, {
        "name": "cloc",
        "description": "A tool that allows for running counting lines of code.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
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
            }
        }
    }, {
        "name": "nglint",
        "description": "A tool that allows for running Angular `ng lint`, that is performing static analysis of TypeScript in Angular projects.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
                "cwd": {
                    "description": "A current working directory where the step is executed.",
                    "default": ".",
                    "type": "string"
                },
            }
        }
    }, {
        "name": "cache",
        "description": "A tool for storing and restoring files from cache.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "required": ["action"],
            "properties": {
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
            }
        }
    }, {
        "name": "gotest",
        "description": "A tool that allows for running Go language tests.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
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
            }
        }
    }, {
        "name": "junit_collect",
        "description": "A tool that allows for collecting test results stored in JUnit files.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "required": ["file_glob"],
            "properties": {
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
        }
    }, {
        "name": "values_collect",
        "description": "A tool that allows for collecting values (metrics, params, etc) from files.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "required": ["files"],
            "properties": {
                "files": {
                    "description": "A list of files.",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {
                                "description": ".",
                                "type": "string"
                            },
                            "namespace": {
                                "description": ".",
                                "type": "string"
                            }
                        }
                    }
                },
                "cwd": {
                    "description": "A current working directory where the step is executed.",
                    "default": ".",
                    "type": "string"
                }
            }
        }
    }, {
        "name": "data",
        "description": "A tool that allows for storing (setting and updating) JSON data server-side.",
        "location": "",
        "entry": "",
        "version": "1",
        "parameters": {
            "properties": {
                "file": {
                    "description": "A file with data with JSON format in case of `set` and `jsonpatch` operations and JQ expression in case of `jq` operation.",
                    "type": "string"
                },
                "cwd": {
                    "description": "A current working directory where the step is executed.",
                    "default": ".",
                    "type": "string"
                },
                "value": {
                    "description": "The sama data as in file field but provided directly. Alternative to file field.",
                    "default": "",
                    "type": "string"
                },
                "operation": {
                    "description":
                        "An operation that should be performed. `set` sets data, `jq` executes JQ expression on server-side data,"
                        " `jsonpatch` patches server-side data, `get` retrieve data from server in JSON format.",
                    "default": "set",
                    "type": "string",
                    "enum": ["set", "jq", "jsonpatch", "get"]
                },
                "json_pointer": {
                    "description": "A JSON pointer that indicates data (see RFC 6901). If `/` then whole data is taken, if key name is provided then data under this key is taken.",
                    "default": "/",
                    "type": "string"
                },
                "scope": {
                    "description":
                       "A scope of data: `flow` - data attached to a flow, `branch-ci` - data attached to a branch but related with CI flows,"
                       " `branch-dev` - data attached to a branch but related with CI flows, `branch` - data attached to a branch,"
                       " `project` - data attached to a project",
                    "default": "flow",
                    "type": "string",
                    "enum": ["flow", "branch-ci", "branch-dev", "branch", "project"]
                }
            }
        }
    }]
    for td in tool_defs:
        tool = Tool.query.filter_by(name=td['name'], version=td['version']).one_or_none()
        if tool is None:
            tool = Tool(name=td['name'],
                        description=td['description'],
                        location=td['location'],
                        entry=td['entry'],
                        version=td['version'],
                        fields=td['parameters'])
            print("   created Tool record", td['name'])
        else:
            tool.name = td['name']
            tool.description = td['description']
            tool.location = td['location']
            tool.entry = td['entry']
            tool.version = td['version']
            tool.fields = td['parameters']
            print("   updated Tool record", td['name'])
        db.session.commit()


def prepare_initial_data():
    print("Preparing initial DB data")

    _prepare_builtin_tools()

    agents_group = AgentsGroup.query.filter_by(name="all").one_or_none()
    if agents_group is None:
        AgentsGroup(name='all')
        db.session.commit()
        print("   created AgentsGroup record 'all'")

        # AgentAssignment(agent=agent, agents_group=agents_group)
        # db.session.commit()
        # print("   created AgentAssignment for record 'all'")

    # Project DEMO
    project = Project.query.filter_by(name="Demo").one_or_none()
    if project is None:
        project = Project(name='Demo', description="This is a demo project.")
        db.session.commit()
        print("   created Project record 'Demo'")

    branch = Branch.query.filter_by(name="Master", project=project).one_or_none()
    if branch is None:
        branch = Branch(name='Master', branch_name='master', project=project)
        db.session.commit()
        print("   created Branch record 'master'")

    for seq_type in [consts.BRANCH_SEQ_FLOW, consts.BRANCH_SEQ_CI_FLOW, consts.BRANCH_SEQ_DEV_FLOW]:
        bs = BranchSequence.query.filter_by(branch=branch, kind=seq_type).one_or_none()
        if bs is None:
            BranchSequence(branch=branch, kind=seq_type, value=0)
    db.session.commit()

    stage = Stage.query.filter_by(name="Tests", branch=branch).one_or_none()
    schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "test",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/Kraken-CI/sample-project-python.git",
                "branch": "master"
            }, {
                "tool": "pytest",
                "cwd": "sample-project-python",
                "params": "-vv",
                "pythonpath": "src"
            }],
            "environments": [{
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }'''
    ctx = prepare_context(branch, {})
    if stage is None:
        stage = Stage(name='Tests', description="This is a stage of tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(schema_code, ctx))
        db.session.commit()
        print("   created Stage record 'Tests'")
    else:
        stage.schema_code = schema_code
        stage.schema = execute_schema_code(schema_code, ctx)
        db.session.commit()


    for seq_type in [consts.BRANCH_SEQ_RUN, consts.BRANCH_SEQ_CI_RUN, consts.BRANCH_SEQ_DEV_RUN]:
        bs = BranchSequence.query.filter_by(branch=branch, stage=stage, kind=seq_type).one_or_none()
        if bs is None:
            BranchSequence(branch=branch, stage=stage, kind=seq_type, value=0)
    db.session.commit()

    # create default users: admin and demo

    admin_user = User.query.filter_by(name="admin").one_or_none()
    if admin_user is None:
        password = pbkdf2_sha256.hash('admin')
        User(name='admin', password=password)
        db.session.commit()
        print("   created User record 'admin'")

    demo_user = User.query.filter_by(name="demo").one_or_none()
    if demo_user is None:
        password = pbkdf2_sha256.hash('demo')
        User(name='demo', password=password)
        db.session.commit()
        print("   created User record 'demo'")

    # common systems
    system = System.query.filter_by(name='any', executor='local').one_or_none()
    if system is None:
        System(name='any', executor='local')
        db.session.commit()

    # preferences
    _prepare_initial_preferences()
