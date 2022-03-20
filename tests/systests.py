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
import time
import requests

KRAKEN_ADDR = os.environ.get('KRAKEN_ADDR', 'localhost:8080')
BASE_URL = 'http://%s/api' % KRAKEN_ADDR

class Session:
    def __init__(self, base_url):
        self.base_url = base_url
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


def test_basic_scenario():
    s = Session(BASE_URL)
    resp = s.login()

    #-------------------------------------------------------------------------
    # check agent authorization

    # get list of authorized agents -> 0
    resp = s.get('/agents', unauthorized=False, start=0, limit=30)
    data = resp.json()
    assert len(data['items']) == 0

    # get list of unauthorized agents -> 1
    resp = s.get('/agents', unauthorized=True, start=0, limit=30)
    data = resp.json()
    assert len(data['items']) == 1

    a_id = data['items'][0]['id']

    # authorize agent
    agents = [{'id': a_id, 'authorized': True, 'disabled': False}]
    resp = s.patch('/agents', agents)
    data = resp.json()

    # get list of authorized agents -> 1
    resp = s.get('/agents', unauthorized=False, start=0, limit=30)
    data = resp.json()
    assert len(data['items']) == 1

    # get list of unauthorized agents -> 0
    resp = s.get('/agents', unauthorized=True, start=0, limit=30)
    data = resp.json()
    assert len(data['items']) == 0

    #-------------------------------------------------------------------------
    # check default project and branch, run its stage
    # wait until it completes successfuly

    # get list of projects and their branches
    resp = s.get('/projects')
    data = resp.json()

    b_id = data['items'][0]['branches'][0]['id']

    # submit a new flow
    data = {}
    resp = s.post('/branches/%d/flows/ci' % b_id, data)
    data = resp.json()
    assert len(data['runs']) == 1

    run_id = data['runs'][0]['id']

    # wait until run completes
    for _  in range(100):
        resp = s.get('/runs/%d' % run_id)
        data = resp.json()
        if data['state'] == 'processed':
            break
        time.sleep(1)

    #-------------------------------------------------------------------------
    # create new project and branch, run a stage with rndtest tool
    # and then run another flow and check if regressions/fixes are present

    # create new project
    data = {'name': 'abc'}
    resp = s.post('/projects', data)
    data = resp.json()

    p_id = data['id']

    # create a branch
    data = {'name': 'def'}
    resp = s.post('/projects/%d/branches' % p_id, data)
    data = resp.json()

    b_id = data['id']

    # create a stage with rndtest tool
    data = {'name': 'ghi',
            'schema_code': '''
def stage(ctx):
    return {
        "parent": "root",
        "triggers": {
            "parent": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "hello world",
            "steps": [{
                "tool": "rndtest"
            }],
            "environments": [{
                "system": "any",
                "agents_group": "all",
                "config": "default"
            }]
        }]
    }'''}
    resp = s.post('/branches/%d/stages' % b_id, data)
    data = resp.json()

    # submit a new flow
    data = {}
    resp = s.post('/branches/%d/flows/ci' % b_id, data)
    data = resp.json()
    assert len(data['runs']) == 1

    run_id = data['runs'][0]['id']

    # wait until run completes
    for _  in range(100):
        resp = s.get('/runs/%d' % run_id)
        data = resp.json()
        if data['state'] == 'processed':
            break
        time.sleep(1)

    assert data['jobs_total'] == 1
    assert data['tests_total'] == 10
    assert data['tests_passed'] > 0
    assert data['regr_cnt'] == 0
    assert data['new_cnt'] == 10
    assert data['fix_cnt'] == 0
    assert data['no_change_cnt'] == 0

    # submit 2nd flow
    data = {}
    resp = s.post('/branches/%d/flows/ci' % b_id, data)
    data = resp.json()
    assert len(data['runs']) == 1

    run_id = data['runs'][0]['id']

    # wait until run completes
    for _  in range(100):
        resp = s.get('/runs/%d' % run_id)
        data = resp.json()
        if data['state'] == 'processed':
            break
        time.sleep(1)

    assert data['jobs_total'] == 1
    assert data['tests_total'] == 10
    assert data['tests_passed'] > 0
    assert data['new_cnt'] == 0
    assert data['fix_cnt'] + data['regr_cnt'] + data['no_change_cnt'] == 10

    # get test case results
    resp = s.get('/runs/%d/results' % run_id)
    data = resp.json()
    assert len(data['items']) == 10
