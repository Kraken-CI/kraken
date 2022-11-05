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

#rom kraken.server import initdb

#rom common import create_app

from kraken.server import schema


@pytest.mark.db
def test_substitute_vars():
    # simple case str->str
    fields = {'f1': 'aaa #{VAR1} ccc'}
    args = {'VAR1': 'bbb'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == new_fields_masked
    assert new_fields == {'f1': 'aaa bbb ccc'}

    # simple case str->str with secret
    fields = {'f1': 'aaa #{VAR1} ccc #{KK_SECRET_abc}'}
    args = {'VAR1': 'bbb', 'KK_SECRET_abc': 'abc'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == {'f1': 'aaa bbb ccc abc'}
    assert new_fields_masked == {'f1': 'aaa bbb ccc ******'}

    # str->dict->str
    fields = {'f1': {'f2': 'aaa #{Var_1} ccc'}}
    args = {'Var_1': 'bbb'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == new_fields_masked
    assert new_fields == {'f1': {'f2': 'aaa bbb ccc'}}

    # str->dict->str with secret
    fields = {'f1': {'f2': 'aaa #{Var_1} ccc #{KK_SECRET_aBc_2}'}}
    args = {'Var_1': 'bbb', 'KK_SECRET_aBc_2': 'cba'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == {'f1': {'f2': 'aaa bbb ccc cba'}}
    assert new_fields_masked == {'f1': {'f2': 'aaa bbb ccc ******'}}

    # str->array[str]
    fields = {'f1': ['aaa #{Var_1} ccc', '#{vAr_2}']}
    args = {'Var_1': 'bbb', 'vAr_2': 'ddd'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == new_fields_masked
    assert new_fields == {'f1': ['aaa bbb ccc', 'ddd']}

    # str->array[str] with secret
    fields = {'f1': ['aaa #{Var_1} ccc', '#{vAr_2}', 'ee #{KK_SECRET_aBc_2} ff']}
    args = {'Var_1': 'bbb', 'vAr_2': 'ddd', 'KK_SECRET_aBc_2': 'cba'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == {'f1': ['aaa bbb ccc', 'ddd', 'ee cba ff']}
    assert new_fields_masked == {'f1': ['aaa bbb ccc', 'ddd', 'ee ****** ff']}

    # str->array[str, dict->str]
    fields = {'f1': ['aaa #{Var_1} ccc', {'f2': '#{vAr_2}'}]}
    args = {'Var_1': 'bbb', 'vAr_2': 'ddd'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == new_fields_masked
    assert new_fields == {'f1': ['aaa bbb ccc', {'f2': 'ddd'}]}

    # str->array[str, dict->str] with secret
    fields = {'f1': ['aaa #{KK_SECRET_Var_1} ccc', {'f2': '#{KK_SECRET_vAr_2}'}]}
    args = {'KK_SECRET_Var_1': 'bbb', 'KK_SECRET_vAr_2': 'ddd'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == {'f1': ['aaa bbb ccc', {'f2': 'ddd'}]}
    assert new_fields_masked == {'f1': ['aaa ****** ccc', {'f2': '******'}]}

    # complex
    fields = {
        "tool": "artifacts #{KK_SECRET_Var}",
        "source": [
            "kraken-#{KK_SECRET_Var}-compose-0.#{KK_FLOW_SEQ}.yaml",
            ".env",
            "server/dist/krakenci_server-0.#{KK_FLOW_SEQ}.tar.gz",
            "agent/krakenci_agent-0.#{KK_FLOW_SEQ}.tar.gz",
            "client/dist/krakenci_client-0.#{KK_FLOW_SEQ}.tar.gz",
            "ui/dist/krakenci_ui-0.#{KK_FLOW_SEQ}.tar.gz",
        ],
        "cwd": "kraken #{KK_SECRET_Var}",
        "public": True,
        "parameters": [{
            "name": "AMI",
            "type": "string #{KK_SECRET_Var}",
            "default": "ami-0967f290f3533e5a8",
            "description": "AMI for Building"
        }]
    }
    args = {'KK_FLOW_SEQ': '123', 'KK_SECRET_Var': 'abc'}
    new_fields, new_fields_masked = schema.substitute_vars(fields, args)
    assert new_fields == {
        'cwd': 'kraken abc',
        'parameters': [{'default': 'ami-0967f290f3533e5a8',
                        'description': 'AMI for Building',
                        'name': 'AMI',
                        'type': 'string abc'}],
        'public': True,
        'source': ['kraken-abc-compose-0.123.yaml',
                   '.env',
                   'server/dist/krakenci_server-0.123.tar.gz',
                   'agent/krakenci_agent-0.123.tar.gz',
                   'client/dist/krakenci_client-0.123.tar.gz',
                   'ui/dist/krakenci_ui-0.123.tar.gz'],
        'tool': 'artifacts abc'}
    assert new_fields_masked == {
        'cwd': 'kraken ******',
        'parameters': [{'default': 'ami-0967f290f3533e5a8',
                        'description': 'AMI for Building',
                        'name': 'AMI',
                        'type': 'string ******'}],
        'public': True,
        'source': ['kraken-******-compose-0.123.yaml',
                   '.env',
                   'server/dist/krakenci_server-0.123.tar.gz',
                   'agent/krakenci_agent-0.123.tar.gz',
                   'client/dist/krakenci_client-0.123.tar.gz',
                   'ui/dist/krakenci_ui-0.123.tar.gz'],
        'tool': 'artifacts ******'}
