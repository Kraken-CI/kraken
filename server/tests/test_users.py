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

from kraken.server import users


@pytest.mark.db
def test_users():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        body = {}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.login(body)

        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        body = {}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body)

        body = {'name': ''}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body)

        body = {'name': 'borat'}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body)

        body = {'name': 'borat', 'password': ''}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body)

        body = {'name': 'borat', 'password': 'pswd'}
        user, code = users.create_user(body)
        assert code == 201
        assert 'id' in user and user['id']
        assert 'name' in user and user['name'] == body['name']
        assert 'enabled' in user and user['enabled'] == True

        body = {'user': 'borat', 'password': 'bad-pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        body = {'user': 'borat', 'password': 'pswd'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']
        assert 'token' in sess and sess['token']
        assert 'user' in sess and sess['user']['id'] == user['id']

        users.logout(sess['id'])

        resp, code = users.get_users()
        assert code == 200
        assert resp and 'total' in resp and resp['total'] == 1
        assert 'items' in resp and len(resp['items']) == 1

        user_id = None
        body = {}
        with pytest.raises(werkzeug.exceptions.NotFound):
            users.change_user_details(user_id, body)

        user_id = user['id']
        body = {}
        user2, code = users.change_user_details(user_id, body)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] == True

        body = {'enabled': False}
        user2, code = users.change_user_details(user_id, body)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] == False

        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        body = {'enabled': True}
        user2, code = users.change_user_details(user_id, body)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] == True

        body = {'user': 'borat', 'password': 'pswd'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']

        body = {'password_old': 'bad-pswd', 'password_new': 'pswd2'}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.change_password(user_id, body)

        body = {'password_old': 'pswd', 'password_new': 'pswd2'}
        users.change_password(user_id, body)

        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        body = {'user': 'borat', 'password': 'pswd2'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']
