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

import os
import sys
import json
import getpass
import zipfile
import tempfile
import urllib.parse

import click
import requests
from tabulate import tabulate


from . import version


class Session:
    def __init__(self, base_url):
        u = urllib.parse.urlparse(base_url)
        port = u.port
        if not port:
            port = ''
        else:
            port = ':%d' % port
        self.base_url = '%s://%s%s/api' % (u.scheme, u.hostname, port)

        self.auth_token = None
        self.user = 'admin'
        if u.username:
            self.user = u.username
        if u.password:
            self.password = u.password
        else:
            self.password = getpass.getpass('Enter password for %s user: ' % self.user)

    def _initial_headers(self):
        h = {}
        if self.auth_token is None:
            return h
        h['Authorization'] = 'Bearer %s' % self.auth_token
        return h

    def get(self, url, exp_status=None, **kwargs):
        url = self.base_url + url
        headers = self._initial_headers()
        resp = requests.request("GET", url, params=kwargs, headers=headers)
        print('GET:', resp.json())
        if exp_status is None:
            assert resp.status_code == 200
        else:
            assert resp.status_code == exp_status
        return resp

    def post(self, url, payload=None, payload_type=False, exp_status=None):
        url = self.base_url + url
        headers = self._initial_headers()

        if payload_type == 'binary':
            resp = requests.request("POST", url, data=payload, headers=headers)
        elif payload_type == 'files':
            resp = requests.request("POST", url, files=payload, headers=headers)
        else:
            resp = requests.request("POST", url, json=payload, headers=headers)

        print('POST:', resp.json())
        if exp_status is None:
            assert resp.status_code in [200, 201]
        else:
            assert resp.status_code == exp_status
        return resp

    def patch(self, url, payload=None, exp_status=None):
        url = self.base_url + url
        headers = self._initial_headers()
        resp = requests.request("PATCH", url, json=payload, headers=headers)
        print('PATCH:', resp.json())
        if exp_status is None:
            assert resp.status_code in [200, 201]
        else:
            assert resp.status_code == exp_status
        return resp

    def login(self):
        payload = {"user": self.user, "password": self.password}
        resp = self.post('/sessions', payload)
        data = resp.json()
        self.auth_token = data['token']
        return resp


def _make_session(server):
    s = Session(server)
    resp = s.login()
    # TODO check resp

    resp = s.get('/version')
    data = resp.json()
    if data['version'] != version.version:
        print('Version mismatch, Kraken Server: %s, kkci client: %s' % (data['version'], version.version))
        print('Please, install proper version of kkci to match Kraken Server version')
        sys.exit(1)
    return s


@click.group()
def main():
    'Kraken Client'


@main.command('version')
def version_():
    'Show kkci, Kraken client, version.'
    print(version.version)


@main.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
def server_version(server):
    'Show Kraken server version.'
    s = _make_session(server)

    resp = s.get('/version')
    data = resp.json()
    print(data['version'])


@main.group()
def tools():
    'Manage Kraken Tools'


@tools.command('list')
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
def list_(server):
    'List registered Kraken Tools'
    s = _make_session(server)

    resp = s.get('/tools')
    data = resp.json()

    tools = []
    for t in data['items']:
        tools.append(dict(id=t['id'],
                          name=t['name'],
                          location=t['location'],
                          entry=t['entry'],
                          version=t['version']))
    print(tabulate(tools, headers={'id': 'Id',
                                   'name': 'Name',
                                   'location': 'Location',
                                   'entry': 'Entry',
                                   'version': 'Version'}))


@tools.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
@click.option('-r', '--version', default=False, is_flag=False, help='Overwrite existing tool version. "latest" version overwrites the latest tool version. If not provided then new version is created.')
@click.argument('tool-file')
def register(server, version, tool_file):
    'Register a new or overwrite existing tool described in indicated TOOL_FILE.'

    # load file and parse as JSON
    with open(tool_file) as fp:
        data = json.load(fp)

    if version:
        data['version'] = version

    s = _make_session(server)
    s.post('/tools', data)


@tools.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
@click.option('-r', '--version', default=False, is_flag=False, help='Overwrite existing tool version. "latest" version overwrites the latest tool version. If not provided then new version is created.')
@click.argument('tool-file')
def upload(server, version, tool_file):
    """Upload tool's code from DIRECTORY to Kraken Server.

    By default new tool version is created (the last version is incremented by 1).
    """

    s = _make_session(server)

    # load file and parse as JSON
    with open(tool_file) as fp:
        tool_meta_data = json.load(fp)

    tool_name = tool_meta_data['name']

    directory = os.path.abspath(os.path.dirname(tool_file))

    with tempfile.NamedTemporaryFile(prefix='kkci-pkg-', suffix='.zip') as tf:
        with zipfile.ZipFile(tf, "w") as pz:
            for root, _, files in os.walk(directory):
                for name in files:
                    if name.endswith(('.pyc', '~')):
                        continue
                    if name == 'tool.zip':
                        continue
                    p = os.path.join(root, name)
                    n = os.path.relpath(p, directory)
                    pz.write(p, arcname=n)

        print('Packed %d files to %s' % (len(pz.namelist()), tf.name))

        with open(tool_file, "rb") as tmf:
            meta = json.load(tmf)

        if version:
            meta['version'] = version

        meta = json.dumps(meta)

        with open(tf.name, "rb") as tbf:

            send_data = {
                'meta': (None, meta, "application/json; charset=UTF-8"),
                'file': ('tool.zip', tbf, "application/zip"),
            }

            url = '/tools/%s/zip' % tool_name
            s.post(url, send_data, payload_type='files')


@main.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
@click.argument('out-file')
def dump_workflow_schema(server, out_file):
    s = _make_session(server)
    resp = s.get('/workflow-schema')
    with open(out_file, "w") as fp:
        json.dump(resp.json(), fp)



if __name__ == '__main__':
    main()
