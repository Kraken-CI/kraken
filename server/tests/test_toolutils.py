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

import pytest
import tempfile
from unittest.mock import patch

import jsonschema

from kraken.server import initdb
from kraken.server.models import db

from common import create_app

from kraken.server import toolutils


def test_check_tool_schema():

    # all ok
    schema = {
        "additionalProperties": False,
        "required": ["pkgs"],
        "properties": {
            "xyz": {
                "description": "Abc.",
                "type": "string"
            },
            "mno": {
                "description": "Abc.",
                "enum": ["g", "h", "i", "j"]
            }
        }
    }
    toolutils.check_tool_schema(schema)

    # bad required
    schema = {
        "additionalProperties": False,
        "required": {"pkgs": "123"},
        "properties": {
            "xyz": {
                "description": "Abc.",
                "type": "string"
            },
            "mno": {
                "description": "Abc.",
                "enum": ["g", "h", "i", "j"]
            }
        }
    }
    with pytest.raises(jsonschema.exceptions.SchemaError) as ex:
        toolutils.check_tool_schema(schema)
    assert "is not of type 'array'" in str(ex.value)

    # no properties
    schema = {
        "additionalProperties": False,
        "required": ["pkgs"]
    }
    with pytest.raises(jsonschema.exceptions.SchemaError) as ex:
        toolutils.check_tool_schema(schema)
    assert "Parameters of tool does not have \'properties\'" in str(ex.value)

    # bad properties type
    schema = {
        "additionalProperties": False,
        "required": ["pkgs"],
        "properties": []
    }
    with pytest.raises(jsonschema.exceptions.SchemaError) as ex:
        toolutils.check_tool_schema(schema)
    assert "is not of type 'object'" in str(ex.value)



@pytest.mark.db
def test_create_or_update_tool():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        # check wrong schema checking
        meta = {
            "name": "abc",
            "description": "Abc.",
            "location": ".",
            "entry": "main",
            "parameters": {
                "additionalProperties": False,
                "required": ["pkgs"],
                "properties": []
            }
        }

        with pytest.raises(jsonschema.exceptions.SchemaError) as ex:
            toolutils.create_or_update_tool(meta)
        assert "is not of type 'object'" in str(ex.value)

        # all, tool abc is created
        meta = {
            "name": "abc",
            "description": "Abc.",
            "location": ".",
            "entry": "main",
            "parameters": {
                "additionalProperties": False,
                "required": ["pkgs"],
                "properties": {
                    "pkgs": {
                        "description": "Abc.",
                        "type": "string"
                    },
                    "provider": {
                        "description": "Abc",
                        "enum": ["a", "b"]
                    }
                }
            }
        }

        tool1 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool1.id > 0
        assert tool1.name == 'abc'
        assert tool1.version == '1'

        # create the second version of tool abc
        tool2 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool2.id > tool1.id
        assert tool2.name == 'abc'
        assert tool2.version == '2'

        # update tool abc version 1
        meta['version'] = '1'
        meta['description'] = 'xyz'
        tool3 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool3.id == tool1.id
        assert tool3.name == 'abc'
        assert tool3.version == '1'
        assert tool3.description == 'xyz'

        # create new arbitrary version dev1 of tool abc
        meta['version'] = 'dev1'
        tool4 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool4.id > tool2.id
        assert tool4.name == 'abc'
        assert tool4.version == 'dev1'

        # create automatically the following version dev2 of tool abc
        del meta['version']
        tool5 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool5.id > tool4.id
        assert tool5.name == 'abc'
        assert tool5.version == 'dev2'

        # create another arbitrary version ghi of tool abc
        meta['version'] = 'ghi'
        tool6 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool6.id > tool5.id
        assert tool6.name == 'abc'
        assert tool6.version == 'ghi'

        # create automatically the following version dev3 to ghi of tool abc
        del meta['version']
        tool7 = toolutils.create_or_update_tool(meta)
        db.session.commit()
        assert tool7.id > tool6.id
        assert tool7.name == 'abc'
        assert tool7.version == 'dev3'


def test_store_tool_in_minio():
    class FakeMc:
        def __init__(self):
            self.po_args = None
            self.po_kwargs = None

        def put_object(self, *args, **kwargs):
            self.po_args = args
            self.po_kwargs = kwargs

    class MyTool:
        id = 4

    tool = MyTool()

    with patch('kraken.server.minioops.get_or_create_minio_bucket_for_tool') as gocmbft:
        mc = FakeMc()
        gocmbft.return_value = ('bkt', mc)

        with tempfile.TemporaryFile() as fp:
            fp.write(b'ghi')
            fp.seek(0)
            toolutils.store_tool_in_minio(fp, tool)

        assert tool.location == 'minio:bkt/tool.zip'
        assert len(mc.po_args) == 4
        assert mc.po_args[0] == 'bkt'
        assert mc.po_args[1] == 'tool.zip'
        assert mc.po_args[2] == fp
        assert mc.po_args[3] == -1
        assert mc.po_kwargs == {'content_type': 'application/zip', 'part_size': 10485760}
