# Copyright 2022-2022 The Kraken Authors
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
import urllib.parse

# LDAP
import ldap
import ldap.filter

# OAuth & OIDC
from authlib.integrations.base_client import BaseOAuth, FrameworkIntegration, OAuth2Mixin, OpenIDMixin, BaseApp
from authlib.integrations.requests_client import OAuth2Session  # OAuth1Session,

from werkzeug.exceptions import Unauthorized
from flask import request, redirect

from .models import db, User, UserSession, get_setting, get_settings_group


log = logging.getLogger(__name__)


def _get_ldap_settings():
    idp_settings = get_settings_group('idp')
    return (idp_settings['ldap_enabled'],
            idp_settings['ldap_server'],
            idp_settings['bind_dn'],
            idp_settings['bind_password'],
            idp_settings['base_dn'],
            idp_settings['search_filter'])


def authenticate_ldap(username, password):
    enabled, ldap_server, bind_dn, bind_pswd, base_dn, search_filter = _get_ldap_settings()
    if not enabled:
        return None
    try:
        conn = ldap.initialize(ldap_server)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.simple_bind_s(bind_dn, bind_pswd)
    except ldap.INVALID_CREDENTIALS as ex:
        conn.unbind_s()
        raise Exception('LDAP: incorrect bind credentials') from ex
    except ldap.SERVER_DOWN as ex:
        raise Exception('LDAP: server is down') from ex

    ldap_filter = search_filter % (ldap.filter.escape_filter_chars(username))
    attrs = ['mail']
    result = conn.search_s(base_dn, ldap.SCOPE_SUBTREE, ldap_filter, attrs)
    if not result:
        conn.unbind_s()
        log.info('ldap: user %s not found or search filter is not ok', username)
        return None

    user = result[0]
    conn.unbind_s()

    conn = ldap.initialize(ldap_server)
    conn.set_option(ldap.OPT_REFERRALS, 0)
    try:
        conn.simple_bind_s(user[0], password)
    except ldap.INVALID_CREDENTIALS:
        log.info('ldap: wrong creds for user %s (%s)', username, user[0])
        return None
    finally:
        conn.unbind_s()

    email_b = user[1].get('mail', [b''])
    email = email_b[0].decode('utf-8')

    return dict(username=username, email=email)


def check_ldap_settings():
    enabled, ldap_server, bind_dn, bind_pswd, _, _ = _get_ldap_settings()
    if not enabled:
        return 'ok'
    try:
        conn = ldap.initialize(ldap_server)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.simple_bind_s(bind_dn, bind_pswd)
    except Exception as ex:
        try:
            conn.unbind_s()
        except Exception:
            pass
        return str(ex)
    return 'ok'


def test_ldap():
    # https://www.forumsys.com/2022/05/10/online-ldap-test-server/
    # ldap.forumsys.com
    resp = authenticate_ldap('gauss', 'password')
                             # 'ldap://ldap.forumsys.com',
                             # 'cn=read-only-admin,dc=example,dc=com',
                             # 'password',
                             # 'dc=example,dc=com',
                             # 'uid=%s')
    print(resp)

    # https://github.com/rroemhild/docker-test-openldap
    # docker run --rm -p 10389:10389 -p 10636:10636 rroemhild/test-openldap
    resp = authenticate_ldap('bender', 'bender')
                             # 'ldap://localhost:10389',
                             # 'cn=admin,dc=planetexpress,dc=com',
                             # 'GoodNewsEveryone',
                             # 'ou=people,dc=planetexpress,dc=com',
                             # '(&(uid=%s)(objectClass=inetOrgPerson))')
    print(resp)

    # https://www.zflexldapadministrator.com/index.php/blog/82-free-online-ldap
    # www.zflexldap.com
    resp = authenticate_ldap('guest1', 'guest1password')
                             # 'ldap://www.zflexldap.com',
                             # 'cn=ro_admin,ou=sysadmins,dc=zflexsoftware,dc=com',
                             # 'zflexpass',
                             # 'ou=guests,dc=zflexsoftware,dc=com',
                             # '(uid=%s)')
    print(resp)


class KrakenOAuth2App(OAuth2Mixin, OpenIDMixin, BaseApp):
    client_cls = OAuth2Session


class KrakenOAuthIntegration(FrameworkIntegration):
    @staticmethod
    def load_config(oauth, name, params):
        return {}


class KrakenOAuth(BaseOAuth):
    # oauth1_client_cls = FlaskOAuth1App
    oauth2_client_cls = KrakenOAuth2App
    framework_integration_cls = KrakenOAuthIntegration


def setup_oauth(id_provider):
    idp_settings = get_settings_group('idp')

    oauth = KrakenOAuth()
    if id_provider == 'google':
        if not idp_settings['google_enabled']:
            raise Exception('Google OIDC/OAuth not enabled')
        idp = oauth.register(name='google',
                             client_id=idp_settings['google_client_id'],
                             client_secret=idp_settings['google_client_secret'],
                             server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                             client_kwargs={'scope': 'openid email profile'})

    elif id_provider == 'microsoft':
        if not idp_settings['microsoft_enabled']:
            raise Exception('Microsoft OIDC/OAuth not enabled')
        idp = oauth.register(name='microsoft',
                             client_id=idp_settings['microsoft_client_id'],
                             client_secret=idp_settings['microsoft_client_secret'],
                             api_base_url='https://graph.microsoft.com/',
                             # server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration',
                             server_metadata_url='https://login.microsoftonline.com/organizations/v2.0/.well-known/openid-configuration',
                             client_kwargs={'scope': 'openid email profile'})

    elif id_provider == 'github':
        if not idp_settings['github_enabled']:
            raise Exception('GitHub OIDC/OAuth not enabled')
        idp = oauth.register(name='github',
                             client_id=idp_settings['github_client_id'],
                             client_secret=idp_settings['github_client_secret'],
                             api_base_url='https://api.github.com/',
                             access_token_url='https://github.com/login/oauth/access_token',
                             authorize_url='https://github.com/login/oauth/authorize',
                             client_kwargs={'scope': 'user:email'},
                             userinfo_endpoint='https://api.github.com/user')

    elif id_provider == 'auth0':
        if not idp_settings['auth0_enabled']:
            raise Exception('Auth0 OIDC/OAuth not enabled')
        idp = oauth.register(name='auth0',
                             client_id=idp_settings['auth0_client_id'],
                             client_secret=idp_settings['auth0_client_secret'],
                             client_kwargs={'scope': 'openid profile email'},
                             server_metadata_url=idp_settings['auth0_openid_config_url'])

    else:
        raise Exception('unsupported identity provider: %s' % id_provider)
    return idp


def authenticate_oidc(id_provider):
    idp = setup_oauth(id_provider)

    server_url = get_setting('general', 'server_url')
    redir_url = urllib.parse.urljoin(server_url, 'bk/oidc-logged')

    state_data = idp.create_authorization_url(redir_url)
    state_data['redirect_uri'] = redir_url
    url = state_data['url']

    return url, state_data


def oidc_logged():
    state = request.args['state']

    us = UserSession.query.filter_by(token=state, deleted=None).one_or_none()
    if us is None:
        raise Unauthorized

    idp = setup_oauth(us.details['idp'])

    if request.method == 'GET':
        error = request.args.get('error')
        if error:
            description = request.args.get('error_description')
            raise Exception("%s: %s" % (error, description))
        params = {
            'code': request.args['code'],
            'state': request.args.get('state'),
        }
    else:
        params = {
            'code': request.form['code'],
            'state': request.form.get('state'),
        }

    kwargs = {}
    claims_options = kwargs.pop('claims_options', None)
    state_data = us.details['state']
    params = idp._format_state_params(state_data, params)
    token = idp.fetch_access_token(**params, **kwargs)

    if 'id_token' in token and 'nonce' in state_data:
        userinfo = idp.parse_id_token(token, nonce=state_data['nonce'], claims_options=claims_options)
    else:
        userinfo = idp.userinfo(token=token)
    token['userinfo'] = userinfo

    user_email = token['userinfo']['email']

    user = User.query.filter_by(name=user_email).one_or_none()
    if not user:
        details = dict(idp=us.details['idp'], email=user_email)
        user = User(name=user_email, password='', details=details)

    us.user = user
    us.token = uuid.uuid4().hex
    db.session.commit()

    resp = redirect('/logged')
    resp.set_cookie('kk_session_token', us.token)

    return resp


def oidc_logout(session_details):
    idp = setup_oauth(session_details['idp'])
    logout_uri = idp.load_server_metadata().get('end_session_endpoint')
    if logout_uri:
        #return_url = url_join(request.url_root, return_url)
        #query = url_encode({'post_logout_redirect_uri': return_url})
        return redirect(logout_uri) # + '?' + query)
    return None



def test_oidc():
    authenticate_oidc('microsoft')


if __name__ == '__main__':
    # test_ldap()
    test_oidc()
