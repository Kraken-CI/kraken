# Copyright 2020-2022 The Kraken Authors
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

from flask import abort
from passlib.hash import pbkdf2_sha256
from werkzeug.exceptions import Unauthorized, BadRequest, NotFound, Forbidden
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified

from .models import db, User, UserSession, Project
from . import utils
from . import access

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

    if 'user' not in creds or 'password' not in creds:
        raise BadRequest('bad credentials')

    # find user for given name with given password
    user = _check_user_password(creds['user'], creds['password'])
    if user is None:
        raise Unauthorized('missing user or incorrect password')

    if user.details and not user.details.get('enabled', True):
        raise Unauthorized('user account is disabled')

    # prepare user session
    us = UserSession(user=user, token=uuid.uuid4().hex)
    db.session.commit()

    roles_data = access.get_user_roles(user)

    resp = us.get_json()
    resp['roles'] = roles_data
    return resp, 201


def logout(session_id, token_info=None):
    if token_info['session'].id != session_id:
        raise Forbidden('only user can logout itself')

    us = UserSession.query.filter_by(id=int(session_id), deleted=None).one_or_none()
    if us is None:
        return None
    us.deleted = utils.utcnow()
    db.session.commit()
    return None


def check_auth_token(token):
    us = UserSession.query.filter_by(token=token, deleted=None).one_or_none()
    if us is None:
        raise Unauthorized
    resp = dict(sub=us.user, session=us)
    return resp


def change_password(user_id, body, token_info=None):
    if token_info['sub'].id != user_id:
        access.check(token_info, '', 'admin', 'only superadmin role can change users passwords')

    user_password = body
    if 'password_new' not in user_password or not user_password['password_new']:
        raise BadRequest('new password cannot be empty')

    user = _check_user_password(int(user_id), user_password['password_old'])

    if user is None:
        raise BadRequest('user not found or old password is incorrect')

    user.password = pbkdf2_sha256.hash(user_password['password_new'])
    db.session.commit()


def create_user(body, token_info=None):
    access.check(token_info, '', 'admin', 'only superadmin role can create users')

    for f in ['name', 'password']:
        if f not in body:
            abort(400, "Missing %s in user" % f)
        if  not body[f]:
            abort(400, "Empty %s in user" % f)

    user = User.query.filter_by(name=body['name']).one_or_none()
    if user is not None:
        abort(400, "User with name %s already exists" % body['name'])

    new_user = User(name=body['name'], password=pbkdf2_sha256.hash(body['password']))
    db.session.commit()

    return new_user.get_json(), 201


def get_users(start=0, limit=30, sort_field="name", sort_dir="asc", token_info=None):
    access.check(token_info, '', 'view', 'only superadmin role can get users')

    q = User.query
    q = q.filter_by(deleted=None)
    q = q.order_by(User.name)

    total = q.count()

    sort_func = asc
    if sort_dir == "desc":
        sort_func = desc

    if sort_field in ['name', 'id']:
        q = q.order_by(sort_func(sort_field))

    q = q.offset(start).limit(limit)

    users = []
    for u in q.all():
        users.append(u.get_json())
    return {'items': users, 'total': total}, 200


def get_user(user_id, token_info=None):
    access.check(token_info, '', 'view', 'only superadmin role can get user')

    q = User.query
    q = q.filter_by(id=user_id)
    q = q.filter_by(deleted=None)
    user = q.one_or_none()

    if user is None:
        raise NotFound('user not found')

    user_data = user.get_json()

    roles_data = access.get_user_roles(user)
    user_data.update(roles_data)

    return user_data, 200


def change_user_details(user_id, body, token_info=None):
    access.check(token_info, '', 'admin', 'only superadmin role can create users')

    q = User.query
    q = q.filter_by(id=user_id)
    q = q.filter_by(deleted=None)
    user = q.one_or_none()

    if user is None:
        raise NotFound('user %s not found' % user_id)

    if not user.details:
        user.details = {}

    if 'enabled' in body:
        if body['enabled']:
            user.details['enabled'] = True
        else:
            user.details['enabled'] = False
        flag_modified(user, 'details')
        db.session.commit()

    enforcer_reloaded = False
    if 'superadmin' in body:
        if not enforcer_reloaded:
            access.enforcer.load_policy()
            enforcer_reloaded = True

        if body['superadmin']:
            access.enforcer.add_named_grouping_policy("g2", str(user.id), access.ROLE_SUPERADMIN)
        else:
            access.enforcer.remove_named_grouping_policy("g2", str(user.id), access.ROLE_SUPERADMIN)
        db.session.commit()

    if 'projects' in body:
        if not enforcer_reloaded:
            access.enforcer.load_policy()
            enforcer_reloaded = True

        for proj_id, role in body['projects'].items():
            q = Project.query
            q = q.filter_by(id=proj_id)
            q = q.filter_by(deleted=None)
            proj = q.one_or_none()
            if proj is None:
                raise NotFound('project %s not found' % proj_id)
            if role not in [access.ROLE_VIEWER, access.ROLE_PWRUSR, access.ROLE_ADMIN, None]:
                raise BadRequest('role %s not supported' % role)

            proj_role_viewer = 'viewer-p%d' % proj.id
            proj_role_pwrusr = 'pwrusr-p%d' % proj.id
            proj_role_admin = 'admin-p%d' % proj.id

            for r in [proj_role_viewer, proj_role_pwrusr, proj_role_admin]:
                access.enforcer.remove_named_grouping_policy("g", str(user.id), r)

            if role == access.ROLE_VIEWER:
                # p, viewer-p1, proj1, view
                access.enforcer.add_policy(proj_role_viewer, str(proj.id), 'view')
                # g, user, viewer-p1
                access.enforcer.add_named_grouping_policy("g", str(user.id), proj_role_viewer)
            elif role == access.ROLE_PWRUSR:
                # p, pwrusr-p1, proj1, view
                access.enforcer.add_policy(proj_role_pwrusr, str(proj.id), 'view')
                # p, pwrusr-p1, proj1, pwrusr
                access.enforcer.add_policy(proj_role_pwrusr, str(proj.id), 'pwrusr')
                # g, user, pwrusr-p1
                access.enforcer.add_named_grouping_policy("g", str(user.id), proj_role_pwrusr)
            elif role == access.ROLE_ADMIN:
                # p, admin-p1, proj1, view
                access.enforcer.add_policy(proj_role_admin, str(proj.id), 'view')
                # p, admin-p1, proj1, pwrusr
                access.enforcer.add_policy(proj_role_admin, str(proj.id), 'pwrusr')
                # p, admin-p1, proj1, admin
                access.enforcer.add_policy(proj_role_admin, str(proj.id), 'admin')
                # g, user, admin-p1
                access.enforcer.add_named_grouping_policy("g", str(user.id), proj_role_admin)
            db.session.commit()

    return user.get_json(), 201
