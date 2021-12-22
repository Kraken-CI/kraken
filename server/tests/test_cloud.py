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

import base64
import logging
import collections
from unittest.mock import patch, Mock

import pytest

from flask import Flask

# import azure
import kubernetes

from kraken.server import consts, initdb
from kraken.server.models import db, System, AgentsGroup
from kraken.server.models import AgentAssignment, Agent, set_setting

from kraken.server.cloud import cloud, k8s

from dbtest import prepare_db

log = logging.getLogger(__name__)




def _create_app():
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
    db.create_all(app=app)

    return app


@pytest.mark.db
def test_check_if_machine_exists_aws_ec2():
    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        agent = Agent(name='agent', address='adr', extra_attrs=dict(instance_id='123'))
        ag = AgentsGroup(name='group', deployment=dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                                                       aws={'region': 'aaa'}))
        AgentAssignment(agent=agent, agents_group=ag)
        db.session.commit()

        # define aws credentials
        set_setting('cloud', 'aws_access_key', 'val')
        set_setting('cloud', 'aws_secret_access_key', 'val')

        # check when vm does not exist
        res = cloud.check_if_machine_exists(ag, agent)
        assert res == False

        # check when vm does exist via mock
        with patch('boto3.resource') as b3r:
            Instance = collections.namedtuple('inst', ['state'])
            b3r.Instance = Instance(state=dict(Name='ok'))

            res = cloud.check_if_machine_exists(ag, agent)
            assert res == True


@pytest.mark.db
def test_check_if_machine_exists_azure():
    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        agent = Agent(name='agent', address='adr', extra_attrs=dict(instance_id='123'))
        ag = AgentsGroup(name='group', deployment=dict(method=consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM,
                                                       azure_vm={'region': 'aaa'}))
        AgentAssignment(agent=agent, agents_group=ag)
        db.session.commit()

        # define azure credentials
        set_setting('cloud', 'azure_subscription_id', 'val')
        set_setting('cloud', 'azure_tenant_id', 'val')
        set_setting('cloud', 'azure_client_id', 'val')
        set_setting('cloud', 'azure_client_secret', 'val')

        # check when vm does not exist
        # with patch('kraken.server.cloud.azure.ComputeManagementClient') as cmc:
        #     # TODO it does not work
        #     cmc.virtual_machines.get.side_effect = Exception('aaa') # azure.core.exceptions.ResourceNotFoundError()

        #     res = cloud.check_if_machine_exists(ag, agent)
        #     assert res == False

        # check when vm does exist
        with patch('kraken.server.cloud.azure.ComputeManagementClient'):
            res = cloud.check_if_machine_exists(ag, agent)
            assert res == True


@pytest.mark.db
def test_check_if_machine_exists_other():
    ag = Mock()
    ag.get_deployment.return_value = (-1, None)
    agent = None

    with pytest.raises(NotImplementedError):
        cloud.check_if_machine_exists(ag, agent)


class Bc3:
    def create_key_pair(self, **kwargs):
        return "aaa"


@pytest.mark.db
def test_create_machines_aws_ec2():
    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        ag = AgentsGroup(name='group', deployment=dict(method=consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2,
                                                       aws={'region': 'aaa', 'instance_type': 'abc'}))
        system = System(name='sys')
        db.session.commit()

        # define aws credentials
        set_setting('cloud', 'aws_access_key', 'val')
        set_setting('cloud', 'aws_secret_access_key', 'val')

        import boto3
        from botocore.stub import Stubber, ANY

        b3r = boto3.resource('ec2')
        stub_r = Stubber(b3r.meta.client)
        stub_r.add_response('run_instances',
                            {'Instances': [{'InstanceId': '123'}]},  # resp
                            {'ImageId': 'sys',
                             'InstanceMarketOptions': {},
                             'InstanceType': 'abc',
                             'KeyName': 'kraken-group',
                             'MaxCount': 1,
                             'MinCount': 1,
                             'Monitoring': {'Enabled': False},
                             'SecurityGroupIds': ['123'],
                             'TagSpecifications': [{'ResourceType': 'instance',
                                                    'Tags': [{'Key': 'kraken-group', 'Value': '%d' % ag.id}]}],
                             'UserData': ANY})  # args
        stub_r.add_response('describe_instances',
                            {'Reservations': [{'Instances': [{'InstanceId': '123',
                                                              'State': {'Code': 16,
                                                                        'Name': 'running'}
                                                              }]}]},  # resp
                            {'InstanceIds': ['123']})  # args
        stub_r.add_response('describe_instances',
                            {'Reservations': [{'Instances': [{'InstanceId': '123',
                                                              'PublicDnsName': 'a.b.c.pl',
                                                              'PrivateIpAddress': '1.2.3.4',
                                                              'PublicIpAddress': '2.3.4.5',
                                                              }]}]},  # resp
                            {'InstanceIds': ['123']})  # args
        stub_r.activate()

        b3c = boto3.client('ec2')
        stub_c = Stubber(b3c)
        stub_c.add_response('create_key_pair',
                            {},  # resp
                            {'KeyName': 'kraken-%s' % ag.name})  # args
        stub_c.add_response('describe_security_groups',
                            {'SecurityGroups': [{'GroupId': '123'}]},  # resp
                            {'GroupNames': ['kraken-%s' % ag.name]})  # args
        stub_c.activate()

        with patch('boto3.client', return_value=b3c), patch('boto3.resource', return_value=b3r):
            cloud.create_machines(ag, system, 1,
                                  'server_url', 'minio_addr', 'clickhouse_addr')



@pytest.mark.db
def test_create_destroy_machines_k8s():
    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        ag = AgentsGroup(name='group', deployment=dict(method=consts.AGENT_DEPLOYMENT_METHOD_K8S,
                                                       kubernetes={}))
        system = System(name='ubuntu:20.04')
        db.session.commit()

        # define k8s credentials
        set_setting('cloud', 'k8s_token', base64.encodebytes(b'token').decode())
        set_setting('cloud', 'k8s_namespace', 'kk')
        set_setting('cloud', 'k8s_api_server_url', 'url')


        # TODO: set proper server_url
        server_url = 'http://192.168.0.89:8080'
        minio_addr = '192.168.0.89:9001'
        clickhouse_addr = '192.168.0.89:9999'

        with patch.object(kubernetes.client.CoreV1Api, 'create_namespaced_pod'), \
             patch.object(kubernetes.client.CoreV1Api, 'list_namespaced_pod') as lnp:

            l = Mock()
            l.items = []
            for _ in range(3):
                p = Mock()
                p.metadata.name = 'name'
                p.status.phase = 'Running'
                p.status.pod_ip = '1.2.3.4'
                p.status.host_ip = '2.3.4.5'
                l.items.append(p)
            lnp.return_value = l

            cloud.create_machines(ag, system, 3,
                              server_url, minio_addr, clickhouse_addr)

        for agent in Agent.query.all():
            with patch.object(kubernetes.client.CoreV1Api, 'delete_namespaced_pod'):
                cloud.destroy_machine(ag, agent)


@pytest.mark.db
def test_check_k8s_settings():
    app = _create_app()

    with app.app_context():
        initdb._prepare_initial_preferences()

        # define k8s credentials
        set_setting('cloud', 'k8s_token', base64.encodebytes(b'token').decode())
        set_setting('cloud', 'k8s_namespace', 'kk')
        set_setting('cloud', 'k8s_api_server_url', 'url')

        with patch.object(kubernetes.client.CoreV1Api, 'read_namespace') as rn, patch('kubernetes.client.VersionApi'):
            ns = Mock()
            ns.status.phase = 'Active'
            rn.return_value = ns
            res = k8s.check_k8s_settings()
            assert res == 'ok'
