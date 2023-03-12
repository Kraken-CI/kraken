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
import sys
import uuid
import inspect

from passlib.hash import pbkdf2_sha256
from flask import Flask

from kraken.server.models import db, User, UserSession
from kraken.server import access

from dbtest import prepare_db


def create_app():
    # addresses
    db_url = prepare_db()

    # Create  Flask app instance
    app = Flask('Kraken Background')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # set KRAKEN_DB_URL that is needed e.g. in jobs.py
    os.environ['KRAKEN_DB_URL'] = db_url

    return app


def prepare_user():
    user = User(name='joe', password=pbkdf2_sha256.hash('password'))
    us = UserSession(user=user, token=uuid.uuid4().hex)
    db.session.commit()
    token_info = dict(sub=user, session=us)

    access.enforcer.add_named_grouping_policy("g2", str(user.id), "superadmin")

    return user, token_info


def check_missing_tests_in_mod(module, test_mod_name):
    mod = sys.modules[test_mod_name]
    src = inspect.getsource(mod)
    for name, func in inspect.getmembers(module, inspect.isfunction):
        if name[0] == "_":
            continue
        if func.__module__ != module.__name__:
            continue
        print('FUNC', name)
        assert name in src, "'%s.%s' API function is not tested, add test for that function" % (module.__name__, name)
