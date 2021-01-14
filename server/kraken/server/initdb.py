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


from .models import db, Branch, Stage, Agent, AgentsGroup, Setting, Tool, Project
from .schema import execute_schema_code

INITIAL_SETTINGS = {
    'general': {
        'server_url': ''
    },
    'notification': {
        'smtp_server': '',
        'smtp_tls': False,
        'smtp_from': '',
        'smtp_user': '',
        'smtp_password': None,  # password
        'slack_token': None  # password
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


def prepare_initial_data():
    print("Preparing initial DB data")

    tool_fields = {
        'git': {'checkout': 'text', 'branch': 'text', 'destination': 'text'},
        'shell': {'cmd': 'text', 'env': 'dict'},
        'pytest': {'params': 'text', 'directory': 'text'},
        'rndtest': {'count': 'text'},
        'artifacts': {'type': 'choice:file', 'upload': 'text'},
        'pylint': {'rcfile': 'text', 'modules_or_packages': 'text'},
        'cloc': {'not-match-f': 'text', 'exclude-dir': 'text'},
        'nglint': {},
        'cache': {},
    }
    tools = {}
    for name, fields in tool_fields.items():
        tool = Tool.query.filter_by(name=name).one_or_none()
        if tool is None:
            tool = Tool(name=name, description="This is a %s tool." % name, fields=fields)
            db.session.commit()
            print("   created Tool record", name)
        tools[name] = tool

    agent = Agent.query.filter_by(name="agent.7").one_or_none()
    if agent is None:
        agent = Agent(name='agent.7', address="agent.7", authorized=False)
        db.session.commit()
        print("   created Agent record 'agent.7'")
    else:
        agent.authorized = False
        db.session.commit()
        print("   Agent 'agent.7' unauthorized")

    agents_group = AgentsGroup.query.filter_by(name="all").one_or_none()
    if agents_group is None:
        agents_group = AgentsGroup(name='all')
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

    stage = Stage.query.filter_by(name="System Tests", branch=branch).one_or_none()
    if stage is None:
        schema_code = '''def stage(ctx):
    return {
        "parent": "Unit Tests",
        "triggers": {
            "parent": True,
            "cron": "1 * * * *",
            "interval": "10m",
            "repository": True,
            "webhook": True
        },
        "parameters": [],
        "configs": [{
            "name": "c1",
            "p1": "1",
            "p2": "3"
        }, {
            "name": "c2",
            "n3": "33",
            "t2": "asdf"
        }],
        "jobs": [{
            "name": "make dist",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/frankhjung/python-helloworld.git",
                "branch": "master"
            }, {
                "tool": "pytest",
                "params": "tests/testhelloworld.py",
                "cwd": "python-helloworld"
            }],
            "environments": [{
                "system": "ubuntu-18.04",
                "agents_group": "all",
                "config": "c1"
            }]
        }]
    }'''
        stage = Stage(name='System Tests', description="This is a stage of system tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        print("   created Stage record 'System Tests'")

    stage = Stage.query.filter_by(name="Unit Tests", branch=branch).one_or_none()
    if stage is None:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [{
            "name": "COUNT",
            "type": "string",
            "default": "10",
            "description": "Number of tests to generate"
        }],
        "jobs": [{
            "name": "random tests",
            "steps": [{
                "tool": "rndtest",
                "count": "#{COUNT}"
            }],
            "environments": [{
                "system": "centos-7",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }'''
        stage = Stage(name='Unit Tests', description="This is a stage of unit tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        print("   created Stage record 'Unit Tests'")

    # Project KRAKEN
    project = Project.query.filter_by(name="Kraken").one_or_none()
    if project is None:
        project = Project(name='Kraken', description="This is a Kraken project.")
        db.session.commit()
        print("   created Project record 'Kraken'")

    branch = Branch.query.filter_by(name="Master", project=project).one_or_none()
    if branch is None:
        branch = Branch(name='Master', branch_name='master', project=project)
        db.session.commit()
        print("   created Branch record 'master'")

    stage = Stage.query.filter_by(name="Static Analysis", branch=branch).one_or_none()
    if stage is None:
        # TODO: pylint
        # }, {
        #     "tool": "pylint",
        #     "rcfile": "../pylint.rc",
        #     "modules_or_packages": "kraken.agent",
        #     "cwd": "kraken/agent"
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pylint",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/Kraken-CI/kraken.git",
                "branch": "master"
            }, {
                "tool": "shell",
                "cmd": "cp server/kraken/server/logs.py server/kraken/server/consts.py agent/kraken/agent",
                "cwd": "kraken"
            }, {
                "tool": "pylint",
                "rcfile": "pylint.rc",
                "modules_or_packages": "agent/kraken/agent",
                "cwd": "kraken"
            }],
            "environments": [{
                "system": "ubuntu-18.04",
                "agents_group": "all",
                "config": "c1"
            }]
        }]
    }'''
        stage = Stage(name='Static Analysis', description="This is a stage of Static Analysis.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        print("   created Stage record 'System Tests'")

    stage = Stage.query.filter_by(name="Unit Tests", branch=branch).one_or_none()
    if stage is None:
        schema_code = '''def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "pytest",
            "steps": [{
                "tool": "git",
                "checkout": "https://github.com/Kraken-CI/kraken.git",
                "branch": "master"
            }, {
                "tool": "shell",
                "cmd": "cp server/kraken/server/logs.py server/kraken/server/consts.py agent/kraken/agent",
                "cwd": "kraken"
            }, {
                "tool": "pytest",
                "params": "-vv",
                "cwd": "kraken/agent"
            }],
            "environments": [{
                "system": "centos-7",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }'''
        stage = Stage(name='Unit Tests', description="This is a stage of unit tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        print("   created Stage record 'Unit Tests'")

    _prepare_initial_preferences()
