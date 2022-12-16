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

from flask import abort, request
from passlib.hash import pbkdf2_sha256
from werkzeug.exceptions import Unauthorized, BadRequest, NotFound, Forbidden
from sqlalchemy.sql.expression import asc, desc
from sqlalchemy.orm.attributes import flag_modified

from .models import db, User, UserSession, Project
from . import utils
from . import access
from . import authn

log = logging.getLogger(__name__)


def _check_user_password(user_id_or_name, password):
    # find user for given name
    q = User.query
    if isinstance(user_id_or_name, str):
        q = q.filter_by(name=user_id_or_name)
    else:
        q = q.filter_by(id=user_id_or_name)
    user = q.filter_by(deleted=None).one_or_none()

    if user:
        # check password
        if not user.password:
            if not user.details:
                return None
            ldap_user = authn.authenticate_ldap(user_id_or_name, password)
            if not ldap_user:
                return None
        elif not pbkdf2_sha256.verify(password, user.password):
            return None
    else:
        ldap_user = authn.authenticate_ldap(user_id_or_name, password)
        if ldap_user:
            details = dict(idp_type='ldap', idp='ldap://ldap.forumsys.com')
            if ldap_user['email']:
                details['email'] = ldap_user['email']
            user = User(name=ldap_user['username'], password='', details=details)
            db.session.commit()

    return user


def login(body):
    if 'method' not in body:
        method = 'local'
    else:
        method = body['method']

    user = None
    details = {}
    redirect_url = None

    if method == 'local':
        if 'user' not in body or 'password' not in body:
            raise BadRequest('bad credentials')

        # find user for given name with given password
        user = _check_user_password(body['user'], body['password'])
        if user is None:
            raise Unauthorized('missing user or incorrect password')
        token = uuid.uuid4().hex

        if user.details and not user.details.get('enabled', True):
            raise Unauthorized('user account is disabled')

    elif method == 'oidc':
        if 'oidc_provider' not in body:
            raise BadRequest('missing OIDC provider')
        if body['oidc_provider'] not in ['google', 'microsoft', 'github', 'auth0']:
            raise BadRequest('bad OIDC provider: %s' % body['oidc_provider'])

        idp = body['oidc_provider']
        redirect_url, state_data = authn.authenticate_oidc(idp)
        token = state_data['state']
        details['idp_type'] = 'oidc'
        details['idp'] = idp
        details['state'] = state_data

    # prepare user session
    us = UserSession(user=user, token=token, details=details)
    db.session.commit()

    resp = us.get_json()

    if user:
        roles_data = access.get_user_roles(user)
        resp['roles'] = roles_data

    if redirect_url:
        resp['redirect_url'] = redirect_url

    return resp, 201


def get_session(session_token, token_info=None):
    if token_info['session'].token != session_token:
        raise Forbidden('only user can get its session data')

    us = UserSession.query.filter_by(token=session_token, deleted=None).one_or_none()
    if us is None:
        raise BadRequest('user session not found')

    resp = us.get_json()
    resp['roles'] = access.get_user_roles(us.user)

    return resp, 200


def logout(session_token, token_info=None):
    if token_info['session'].token != session_token:
        raise Forbidden('only user can logout itself')

    us = UserSession.query.filter_by(token=session_token, deleted=None).one_or_none()
    if us is None:
        return None
    us.deleted = utils.utcnow()
    db.session.commit()

    if us.details and 'idp_type' in us.details and us.details['idp_type'] == 'oidc':
        authn.oidc_logout(us.details)

    return None


def check_auth_token(token):
    us = UserSession.query.filter_by(token=token, deleted=None).one_or_none()
    if us is None:
        raise Unauthorized
    resp = dict(sub=us.user, session=us)
    return resp


def get_token_info_from_request():
    token = request.headers.get('Authorization', None)
    if token:
        token = token.replace('Bearer ', '')
    else:
        token = request.cookies.get('kk_session_token')
    if not token:
        return None
    token_info = check_auth_token(token)
    return token_info


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
    policy_changed = False
    if 'superadmin' in body:
        policy_changed = True
        if not enforcer_reloaded:
            access.enforcer.load_policy()
            enforcer_reloaded = True

        if body['superadmin']:
            access.enforcer.add_named_grouping_policy("g2", str(user.id), access.ROLE_SUPERADMIN)
        else:
            access.enforcer.remove_named_grouping_policy("g2", str(user.id), access.ROLE_SUPERADMIN)
        db.session.commit()

    if 'projects' in body:
        policy_changed = True
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

    if policy_changed:
        access.notify_policy_change()

    user_data = user.get_json()
    roles_data = access.get_user_roles(user)
    user_data.update(roles_data)

    return user_data, 201
