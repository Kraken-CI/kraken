# Copyright 2020-2021 The Kraken Authors
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

import sqlalchemy

from kraken.server.models import db

def create_empty_db(db_name, drop_exisiting=False):
    db_root_url = os.environ.get('POSTGRES_URL', 'postgresql://kk:kk@localhost:15432/')

    # check if db exists
    engine = sqlalchemy.create_engine(db_root_url + db_name, echo=False)
    db_exists = False
    try:
        connection = engine.connect()
        connection.execute('select 1')
        connection.close()
        db_exists = True
    except Exception:
        pass

    engine = sqlalchemy.create_engine(db_root_url, echo=False)
    connection = engine.connect()

    if db_exists and drop_exisiting:
        connection.execute("commit;")
        connection.execute("DROP DATABASE %s;" % db_name)
        db_exists = False

    # create db if missing
    if not db_exists:
        connection.execute("commit;")
        connection.execute("CREATE DATABASE %s;" % db_name)

    connection.close()

    return db_root_url, db_exists


def clear_db_postresql(connection):
    for table in db.metadata.tables.keys():
        connection.execute('ALTER TABLE "%s" DISABLE TRIGGER ALL;' % table)
        try:
            connection.execute('DELETE FROM "%s";' % table)
        except Exception as e:
            if not "doesn't exist" in str(e):
                raise
        connection.execute('ALTER TABLE "%s" ENABLE TRIGGER ALL;' % table)


def prepare_db(db_name=None):
    # session.close_all()
    # if metadata.bind:
    #     metadata.bind.dispose()

    if db_name is None:
        db_name = os.environ.get('KK_UT_DB', 'kkut')

    # db_root_url, db_exists = create_empty_db(db_name)
    db_root_url, _ = create_empty_db(db_name)

    # prepare connection, create any missing tables
    #clean_db()
    real_db_url = db_root_url + db_name
    # engine = sqlalchemy.create_engine(real_db_url, echo=False)
    # db.metadata.bind = engine
    # db.setup_all()
    # db.create_all()
    # db.fix_compatibility()

    # if db_exists:
    #     global_log.log_global('prepare_db - delete all rows', 'real_db_url', real_db_url)
    #     # delete all rows from all tables
    #     if db_url.startswith("mysql"):
    #         clear_db_mysql(engine)
    #     elif db_url.startswith("postgresql"):
    #         clear_db_postresql(engine)

    # db.prepare_indexes(engine)
    return real_db_url
