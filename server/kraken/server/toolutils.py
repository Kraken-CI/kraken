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

import re

from sqlalchemy.sql.expression import desc
import jsonschema

from .models import Tool
from . import minioops


def check_tool_schema(schema):
    try:
        jsonschema.validate(instance={}, schema=schema)
    except jsonschema.exceptions.SchemaError:
        raise
    except Exception:
        pass

    if "properties" not in schema:
        raise jsonschema.exceptions.SchemaError("Parameters of tool does not have 'properties' field.")

    required_fields = schema.get("required", [])
    if not isinstance(required_fields, list):
        raise jsonschema.exceptions.SchemaError("'required' field in tool fields definitions should have list value, not %s." % type(required_fields))


def create_or_update_tool(meta):
    name = meta['name']
    description = meta['description']
    location = meta['location']
    entry = meta['entry']
    fields = meta['parameters']
    version = meta.get('version', None)

    # check tool schema if it is ok
    check_tool_schema(fields)

    tool = None
    if version:
        # find tool to overwrite
        q = Tool.query
        q = q.filter_by(name=name)
        q = q.filter_by(version=version)
        q = q.filter_by(deleted=None)
        tool = q.one_or_none()
    else:
        # fint the latest tool to estimate next version
        q = Tool.query
        q = q.filter_by(name=name)
        q = q.filter_by(deleted=None)
        q = q.order_by(desc(Tool.created))
        tools = q.all()
        prev_tool = None
        for t in tools:
            if t.version[-1].isdigit():
                prev_tool = t
                break

    if not version:
        if not prev_tool:
            version = '1'
        else:
            m = re.match(r'^(.*)(\d+)$', prev_tool.version)
            if not m:
                version = '1'
            else:
                ver_base = m.group(1)
                ver_num = int(m.group(2))
                ver_num += 1
                version = '%s%d' % (ver_base, ver_num)

    if tool:
        tool.description = description
        tool.version = version
        tool.location = location
        tool.entry = entry
        tool.fields = fields
    else:
        tool = Tool(name=name, description=description, version=version, location=location, entry=entry, fields=fields)

    return tool


def store_tool_in_minio(tool_zip_fp, tool):
    bucket, mc = minioops.get_or_create_minio_bucket_for_tool(tool.id)
    dest = 'tool.zip'

    mc.put_object(bucket, dest, tool_zip_fp, -1, part_size=10*1024*1024, content_type="application/zip")

    tool.location = 'minio:%s/%s' % (bucket, dest)

    return tool
