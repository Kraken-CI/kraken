# Copyright 2020 The Kraken Authors
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

import uuid
import logging
import datetime

from passlib.hash import pbkdf2_sha256
from werkzeug.exceptions import Unauthorized, BadRequest

from .models import db, User, UserSession

log = logging.getLogger(__name__)


def _check_user_password(user_id_or_name, password):
    # find user for given name
    q = User.query
    if isinstance(user_id_or_name, str):
        q = q.filter_by(name=user_id_or_name)
    else:
        q = q.filter_by(id=user_id_or_name)
    user = q.filter_by(deleted=None).one_or_none()
    if user is None:
        return None

    # check password
    if not pbkdf2_sha256.verify(password, user.password):
        return None

    return user

def login(body):
    creds = body
    # find user for given name with given password
    user = _check_user_password(creds['user'], creds['password'])
    if user is None:
        return None

    # prepare user session
    us = UserSession(user=user, token=uuid.uuid4().hex)
    db.session.commit()

    return us.get_json(), 201


def logout(session_id):
    us = UserSession.query.filter_by(id=int(session_id), deleted=None).one_or_none()
    if us is None:
        return None
    us.deleted = datetime.datetime.utcnow()
    db.session.commit()
    return None


def check_auth_token(token):
    us = UserSession.query.filter_by(token=token, deleted=None).one_or_none()
    if us is None:
        raise Unauthorized
    resp = dict(sub=us.user, session=us)
    return resp


def change_password(user_id, user_password):
    if 'password_new' not in user_password or not user_password['password_new']:
        raise BadRequest('new password cannot be empty')

    user = _check_user_password(int(user_id), user_password['password_old'])

    if user is None:
        raise BadRequest('user not found or old password is incorrect')

    user.password = pbkdf2_sha256.hash(user_password['password_new'])
    db.session.commit()
