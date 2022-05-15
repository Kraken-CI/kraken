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

import json

import click
import requests
from tabulate import tabulate


class Session:
    def __init__(self, base_url):
        self.base_url = base_url + '/api'
        self.auth_token = None

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

    def post(self, url, payload=None, exp_status=None):
        url = self.base_url + url
        headers = self._initial_headers()
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

    def login(self, user='admin', password='admin'):
        payload = {"user": user, "password": password}
        resp = self.post('/sessions', payload)
        data = resp.json()
        self.auth_token = data['token']
        return resp


@click.group()
def main():
    'Kraken Client'


@main.group()
def tools():
    'Manage Kraken Tools'


def _make_session(server):
    s = Session(server)
    resp = s.login()
    # TODO check resp
    return s

@tools.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
def list(server):
    'List registered Kraken Tools'
    s = _make_session(server)

    resp = s.get('/tools')
    data = resp.json()

    tools = data['items']
    print(tabulate(tools, headers={'id': 'Id', 'name': 'Name'}))


@tools.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Kraken Server URL')
@click.argument('tool-file')
def register(server, tool_file):
    'Register a new tool describe in indicated TOOL_FILE.'

    # load file and parse as JSON
    with open(tool_file) as fp:
        data = json.load(fp)

    s = _make_session(server)
    resp = s.post('/tools', data)


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
