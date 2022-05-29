# Copyright 2022 The Kraken Authors
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

import datetime

import pytest
from hamcrest import assert_that, has_entries, matches_regexp, contains_exactly, instance_of

import werkzeug.exceptions

from kraken.server import consts, initdb, utils
from kraken.server.models import db, Project, Branch, Flow

from common import create_app

from kraken.server import schemaval


@pytest.mark.db
def test_validate():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        initdb._prepare_builtin_tools()

        #proj1 = Project(name='proj-1')
        #proj2 = Project(name='proj-2')
        #br = Branch(name='br', project=proj1)
        #db.session.commit()

        # all ok
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "tool": "shell",
                    "cmd": "ls -al"
                }],
                "environments": [{
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert result is None

        # missing tool in step
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "cmd": "ls -al"
                }],
                "environments": [{
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert result == "Missing 'tool' field in the 1st job pkg, in the 1st step"

        # unknown abc tool in step
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "tool": "abc",
                    "cmd": "ls -al"
                }],
                "environments": [{
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert result == "Unknown tool 'abc' in the 1st job pkg, in the 1st step"

        # all ok - tool with version
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "tool": "shell@1",
                    "cmd": "ls -al"
                }],
                "environments": [{
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert result is None

        # tool with wrong params
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "tool": "shell",
                    "abc": "ls -al"
                }],
                "environments": [{
                    "system": "any",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert "'abc' was unexpected" in result

        # advanced example - all ok
        instance = {
            "parent": "root",
            "triggers": {
                "parent": True,
            },
            "parameters": [],
            "configs": [],
            "jobs": [{
                "name": "pkg",
                "steps": [{
                    "tool": "shell",
                    "cmd": "ls -al"
                }, {
                    "tool": "local_tool",
                    "tool_location": "/home/godfryd/repos/kraken/pkg-tool",
                    "tool_entry": "main",
                    "pkgs": "vim"
                }],
                "environments": [{
                   "system": "any",
                   "agents_group": "all",
                   "config": "default"
               }, {
                   "executor": "docker",
                   "system": "krakenci/ubuntu:20.04",
                   "agents_group": "all",
                   "config": "default"
               }, {
                    "executor": "lxd",
                    "system": "ubuntu/focal/amd64",
                    "agents_group": "all",
                    "config": "default"
                }]
            }]
        }

        result = schemaval.validate(instance)
        assert result is None
