# Copyright 2021 The Kraken Authors
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

import os
import subprocess
from urllib.parse import urlparse
from unittest.mock import MagicMock

import pytest

from flask import Flask
from sqlalchemy import create_engine, Table, Column, Unicode, MetaData, Boolean, Integer
from sqlalchemy import ForeignKey, Index, DateTime, Text, UnicodeText, String
from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION, BYTEA

from kraken.server import consts
from kraken.server.models import db
from kraken.migrations import apply as migrations

from dbtest import prepare_db  # , clear_db_postresql


@pytest.mark.db
def test_create_db_at_once():
    db_url = prepare_db()

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)
    db.create_all(app=app)

    o = urlparse(db_url)
    env = os.environ.copy()
    env['PGPASSWORD'] = o.password
    cmd = 'pg_dump -U %s -h %s -p %s -d %s' % (o.username, o.hostname, o.port, o.path[1:])
    cmd = 'bash -c "%s"' % cmd
    subprocess.run(cmd, shell=True,  env=env, capture_output=True, check=True)

    # clear_db_postresql(db)


@pytest.mark.db
def test_compare_create_db():
    # create schema at once based on models.py
    db_url = prepare_db('kkut_once')
    os.environ['KRAKEN_DB_URL'] = db_url

    migrations.main()

    o = urlparse(db_url)
    env = os.environ.copy()
    env['PGPASSWORD'] = o.password
    cmd = 'pg_dump -U %s -h %s -p %s -d %s -s' % (o.username, o.hostname, o.port, o.path[1:])
    cmd = 'bash -c "%s"' % cmd
    p = subprocess.run(cmd, shell=True,  env=env, text=True, capture_output=True, check=True)
    schema_once = p.stdout
    # with open('/tmp/once.sql', 'w') as f:
    #     f.write(schema_once)

    # create schema using migrations
    db_url = prepare_db('kkut_migr')
    os.environ['KRAKEN_DB_URL'] = db_url

    engine = create_engine(db_url)
    conn = engine.connect()
    meta = MetaData()

    # prepare initial schema crafted by hand
    alembic_version_tbl = Table(
        'alembic_version', meta,
        Column('version_num', Unicode(length=32), nullable=False, primary_key=True))

    Table('stages', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50)),
          Column('description', Unicode(1024)),
          Column('branch_id', Integer, ForeignKey('branches.id'), nullable=False),
          Column('enabled', Boolean, default=True),
          Column('schema', JSONB, nullable=False),
          Column('schema_code', UnicodeText),
          Column('triggers', JSONB),
          Column('webhooks', JSONB))

    Table('projects', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50)),
          Column('description', Unicode(200)),
          Column('enabled', Boolean, default=True))

    Table('issues', meta,
          Column('id', Integer, primary_key=True),
          Column('issue_type', Integer),
          Column('line', Integer),
          Column('column', Integer),
          Column('path', Unicode(512)),
          Column('symbol', Unicode(64)),
          Column('message', Unicode(256)),
          Column('job_id', Integer, ForeignKey('jobs.id'), nullable=False))

    Table('branches', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(255)),
          Column('project_id', Integer, ForeignKey('projects.id'), nullable=False),
          Column('branch_name', Unicode(255)))

    Table('flows', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('finished', DateTime),
          Column('state', Integer, default=consts.FLOW_STATE_IN_PROGRESS),
          Column('kind', Integer),
          Column('branch_name', Unicode(255)),
          Column('branch_id', Integer, ForeignKey('branches.id'), nullable=False),
          #Column('trigger_data', JSONB, nullable=False),
          Column('args', JSONB, nullable=False))

    Table('runs', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('started', DateTime),
          Column('finished', DateTime),
          Column('finished_again', DateTime),
          Column('state', Integer),
          Column('email_sent', DateTime),
          Column('note', UnicodeText),
          Column('stage_id', Integer, ForeignKey('stages.id'), nullable=False),
          Column('flow_id', Integer, ForeignKey('flows.id'), nullable=False),
          Column('hard_timeout_reached', DateTime),
          Column('soft_timeout_reached', DateTime),
          Column('args', JSONB, nullable=False),
          Column('trigger_data', Integer))

    Table('steps', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('index', Integer, nullable=False),
          Column('job_id', Integer, ForeignKey('jobs.id'), nullable=False),
          Column('tool_id', Integer, ForeignKey('tools.id'), nullable=False),
          Column('fields', JSONB, nullable=False),
          Column('result', JSONB),
          Column('status', Integer))

    Table('executors', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50), nullable=False),
          Column('address', Unicode(25), index=True, nullable=False),
          Column('ip_address', Unicode(50)),
          Column('state', Integer, default=0),
          Column('disabled', Boolean, default=False),
          Column('comment', Text),
          Column('status_line', Text),
          #Column('extra_attrs', JSONB),
          Column('job_id', Integer, ForeignKey('jobs.id')))

    Table('executor_groups', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50)),
          Column('project_id', Integer, ForeignKey('projects.id'), nullable=False))

    Table('executor_assignments', meta,
          Column('executor_id', Integer, ForeignKey('executors.id'), primary_key=True),
          Column('executor_group_id', Integer, ForeignKey('executor_groups.id'), primary_key=True))

    Table('jobs', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(200)),
          Column('assigned', DateTime),
          Column('started', DateTime),
          Column('finished', DateTime),
          Column('processing_started', DateTime),
          Column('completed', DateTime),
          Column('run_id', Integer, ForeignKey('runs.id'), nullable=False),
          Column('state', Integer),
          Column('completion_status', Integer),
          Column('covered', Boolean),
          Column('notes', Unicode(2048)),
          Column('executor_used_id', Integer, ForeignKey('executors.id')),
          Column('executor_group_id', Integer, ForeignKey('executor_groups.id'), nullable=False))

    Table('preferences', meta,
          Column('id', Integer, primary_key=True))

    Table('settings', meta,
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50)),
          Column('value', Text),
          Column('val_type', String(8)))

    Table('test_cases', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(255), unique=True),
          Column('tool_id', Integer, ForeignKey('tools.id'), nullable=False))

    Table('test_case_results', meta,
          Column('id', Integer, primary_key=True),
          Column('test_case_id', Integer, ForeignKey('test_cases.id'), nullable=False),
          Column('job_id', Integer, ForeignKey('jobs.id'), nullable=False),
          Column('result', Integer),
          Column('values', JSONB),
          Column('cmd_line', UnicodeText),
          Column('instability', Integer),
          Column('age', Integer),
          Column('change', Integer))

    Table('tools', meta,
          Column('created', DateTime, nullable=False),
          Column('updated', DateTime, nullable=False),
          Column('deleted', DateTime),
          Column('id', Integer, primary_key=True),
          Column('name', Unicode(50)),
          Column('description', Unicode(200)),
          Column('configuration', Text),
          Column('fields', JSONB, nullable=False))

    Table('apscheduler_jobs', meta,
          Column('id', Unicode(191), nullable=False, primary_key=True),
          #Column('next_run_time', double precision,
          #Column('job_state', bytea NOT NULL)
          Column('next_run_time', DOUBLE_PRECISION(precision=53), nullable=True, index=True, unique=False),
          Column('job_state', BYTEA, nullable=False))

    meta.create_all(engine)

    ins = alembic_version_tbl.insert().values(version_num='0731897c862e')  # this is first migration
    conn.execute(ins)

    migrations.main()

    o = urlparse(db_url)
    env = os.environ.copy()
    env['PGPASSWORD'] = o.password
    cmd = 'pg_dump -U %s -h %s -p %s -d %s -s' % (o.username, o.hostname, o.port, o.path[1:])
    cmd = 'bash -c "%s"' % cmd
    p = subprocess.run(cmd, shell=True,  env=env, text=True, capture_output=True, check=True)
    schema_migr = p.stdout
    # with open('/tmp/migr.sql', 'w') as f:
    #     f.write(schema_migr)

    # compare dumped schemas
    assert schema_once.splitlines() == schema_migr.splitlines()
