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

import werkzeug.exceptions

from kraken.server import initdb, access
from kraken.server.models import User, UserSession

from common import create_app, prepare_user, check_missing_tests_in_mod

from kraken.server import users


def test_missing_tests():
    check_missing_tests_in_mod(users, __name__)


@pytest.mark.db
def test_check_auth_token():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()

        token = 'bad'
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            resp = users.check_auth_token(token)

        _, token_info = prepare_user()
        token = token_info['session'].token
        resp = users.check_auth_token(token)
        assert resp['sub'] == token_info['sub']


@pytest.mark.db
def test_users():
    app = create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()
        access.init()
        _, token_info = prepare_user()

        # login: empty body - bad request
        body = {}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.login(body)

        # login: incorrect creds (non-existing) - unauthorized
        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        # create user: empty body - bad request
        body = {}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body, token_info=token_info)

        # create user: empty name field - bad request
        body = {'name': ''}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body, token_info=token_info)

        # create user: no password field - bad request
        body = {'name': 'borat'}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body, token_info=token_info)

        # create user: empty password field - bad request
        body = {'name': 'borat', 'password': ''}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.create_user(body, token_info=token_info)

        # create user: all ok
        body = {'name': 'borat', 'password': 'pswd'}
        user, code = users.create_user(body, token_info=token_info)
        assert code == 201
        assert 'id' in user and user['id']
        assert 'name' in user and user['name'] == body['name']
        assert 'enabled' in user and user['enabled'] is True

        # login: incorrect creds - bad request
        body = {'user': 'borat', 'password': 'bad-pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        # login: all ok
        body = {'user': 'borat', 'password': 'pswd'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']
        assert 'token' in sess and sess['token']
        assert 'user' in sess and sess['user']['id'] == user['id']

        user_rec = User.query.filter_by(id=user['id']).one()
        us_rec = UserSession.query.filter_by(id=sess['id']).one()

        token_info2 = dict(sub=user_rec, session=us_rec)

        # get session
        sess2, code = users.get_session(sess['token'], token_info=token_info2)
        assert code == 200
        assert sess2['token'] == sess['token']
        assert sess2['id'] == sess['id']

        # logout: all ok
        users.logout(sess['token'], token_info=token_info2)

        # get users, 2 present
        resp, code = users.get_users(token_info=token_info)
        assert code == 200
        assert resp and 'total' in resp and resp['total'] == 2
        assert 'items' in resp and len(resp['items']) == 2

        # update user: bad user id - not found
        user_id = None
        body = {}
        with pytest.raises(werkzeug.exceptions.NotFound):
            users.change_user_details(user_id, body, token_info=token_info)

        # update user: no changes - all ok
        user_id = user['id']
        body = {}
        user2, code = users.change_user_details(user_id, body, token_info=token_info)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] is True

        # update user: disable user - all ok
        body = {'enabled': False}
        user2, code = users.change_user_details(user_id, body, token_info=token_info)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] is False

        # login disabled user - should raise unauthorized
        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        # update user: re-enable user - all ok
        body = {'enabled': True}
        user2, code = users.change_user_details(user_id, body, token_info=token_info)
        assert code == 201
        assert 'enabled' in user2 and user2['enabled'] is True

        # login re-enabled user - should be ok
        body = {'user': 'borat', 'password': 'pswd'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']

        body = {'password_old': 'bad-pswd', 'password_new': 'pswd2'}
        with pytest.raises(werkzeug.exceptions.BadRequest):
            users.change_password(user_id, body, token_info=token_info)

        body = {'password_old': 'pswd', 'password_new': 'pswd2'}
        users.change_password(user_id, body, token_info=token_info2)

        body = {'user': 'borat', 'password': 'pswd'}
        with pytest.raises(werkzeug.exceptions.Unauthorized):
            users.login(body)

        body = {'user': 'borat', 'password': 'pswd2'}
        sess, code = users.login(body)
        assert code == 201
        assert sess and 'id' in sess and sess['id']
