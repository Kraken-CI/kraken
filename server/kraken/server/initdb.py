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

from passlib.hash import pbkdf2_sha256

from .models import db, Branch, Stage, AgentsGroup, Setting, Tool, Project
from .models import User, BranchSequence
from .schema import execute_schema_code
from . import consts


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
    },
    'monitoring': {
        'sentry_dsn': None  # password
    },
    'cloud': {
        'aws_access_key': '',
        'aws_secret_access_key': None  # password
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
        'gotest': {},
        'junit_collect': {},
    }
    tools = {}
    for name, fields in tool_fields.items():
        tool = Tool.query.filter_by(name=name).one_or_none()
        if tool is None:
            tool = Tool(name=name, description="This is a %s tool." % name, fields=fields)
            db.session.commit()
            print("   created Tool record", name)
        tools[name] = tool

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
    if stage is None:
        stage = Stage(name='Tests', description="This is a stage of tests.", branch=branch,
                      schema_code=schema_code, schema=execute_schema_code(branch, schema_code))
        db.session.commit()
        print("   created Stage record 'Tests'")
    else:
        stage.schema_code = schema_code
        stage.schema = execute_schema_code(branch, schema_code)
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

    _prepare_initial_preferences()
