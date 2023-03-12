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
from sqlalchemy import text

from kraken.server.models import db

def create_empty_db(db_name, drop_exisiting=False):
    db_root_url = os.environ.get('POSTGRES_URL', 'postgresql://kk:kk@localhost:15432/')

    # check if db exists
    engine = sqlalchemy.create_engine(db_root_url + db_name, echo=False)
    db_exists = False
    try:
        with engine.begin() as connection:
            connection.execute(text('select 1'))
        db_exists = True
    except Exception:
        pass

    engine = sqlalchemy.create_engine(db_root_url, echo=False)

    with engine.begin() as connection:
        if db_exists and drop_exisiting:
            connection.execute(text("commit;"))
            connection.execute(text("DROP DATABASE %s;" % db_name))
            db_exists = False

        # create db if missing
        if not db_exists:
            connection.execute(text("commit;"))
            connection.execute(text("CREATE DATABASE %s;" % db_name))

    return db_root_url, db_exists


def clear_db_postresql(connection):
    for table in db.metadata.tables.keys():
        try:
            connection.execute(text('ALTER TABLE "%s" DISABLE TRIGGER ALL;' % table))
            connection.execute(text('DELETE FROM "%s";' % table))
            connection.execute(text('ALTER TABLE "%s" ENABLE TRIGGER ALL;' % table))
        except Exception as e:
            connection.execute(text('ROLLBACK'))
            if not "doesn't exist" in str(e) and not 'does not exist' in str(e):
                raise


def prepare_db(db_name=None):
    # session.close_all()
    # if metadata.bind:
    #     metadata.bind.dispose()

    if db_name is None:
        db_name = os.environ.get('KK_UT_DB', 'kkut')

    db_root_url, db_exists = create_empty_db(db_name)

    # prepare connection, create any missing tables
    #clean_db()
    real_db_url = db_root_url + db_name

    if db_exists:
        # delete all rows from all tables
        engine = sqlalchemy.create_engine(real_db_url, echo=False)
        with engine.begin() as connection:
            clear_db_postresql(connection)

    # db.prepare_indexes(engine)
    return real_db_url
