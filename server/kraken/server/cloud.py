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

import logging

import boto3
import botocore
import requests
from sqlalchemy.orm.attributes import flag_modified

from .models import db
from .models import Agent, AgentAssignment, get_setting
from . import utils

log = logging.getLogger(__name__)


def check_aws_settings():
    access_key = get_setting('cloud', 'aws_access_key')
    if not access_key:
        return 'AWS access key is empty'
    if len(access_key) < 16:
        return 'AWS access key is too short'
    if len(access_key) > 128:
        return 'AWS access key is too long'

    secret_access_key = get_setting('cloud', 'aws_secret_access_key')
    if not secret_access_key:
        return 'AWS secret access key is empty'
    if len(secret_access_key) < 36:
        return 'AWS secret access key is too short'

    try:
        ec2 = boto3.client('ec2', region_name='us-east-1', aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
        ec2.describe_regions()
    except Exception as ex:
        return str(ex)

    return 'ok'


def allocate_ec2_vms(aws, access_key, secret_access_key,
                     ag, system, num,
                     server_url, minio_addr, clickhouse_addr):
    region = aws['region']
    ec2 = boto3.client("ec2", region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)
    ec2_res = boto3.resource('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_access_key)

    # get key pair
    if not ag.extra_attrs:
        ag.extra_attrs = {}
    if 'aws' not in ag.extra_attrs:
        ag.extra_attrs['aws'] = {}
    if 'key-pair' not in ag.extra_attrs['aws']:
        key_name = 'kraken-%s' % ag.name
        try:
            key_pair = ec2.create_key_pair(KeyName=key_name)
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'InvalidKeyPair.Duplicate':
                ec2.delete_key_pair(KeyName=key_name)
                key_pair = ec2.create_key_pair(KeyName=key_name)
            else:
                log.exception('problem with creating AWS key pair')
                return
        ag.extra_attrs['aws']['key-pair'] = key_pair
        flag_modified(ag, 'extra_attrs')
        db.session.commit()
    else:
        key_name = ag.extra_attrs['aws']['key-pair']['KeyName']

    # prepare security group
    grp_name = 'kraken-%s' % ag.name
    sec_grp = None
    try:
        sec_grp = ec2.describe_security_groups(GroupNames=[grp_name])
    except Exception:
        log.exception('IGNORED EXCEPTION')
    if not sec_grp:
        rsp = requests.get('https://checkip.amazonaws.com')
        my_ip = rsp.text.strip()

        default_vpc = list(ec2_res.vpcs.filter(Filters=[{'Name': 'isDefault', 'Values': ['true']}]))[0]
        sec_grp = default_vpc.create_security_group(GroupName=grp_name,
                                                    Description='kraken sec group that allows only incomming ssh')
        ip_perms = [{
            # SSH ingress open to only the specified IP address
            'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
            'IpRanges': [{'CidrIp': '%s/32' % my_ip}]}]
        sec_grp.authorize_ingress(IpPermissions=ip_perms)
        sec_grp_id = sec_grp.id
    else:
        sec_grp_id = sec_grp['SecurityGroups'][0]['GroupId']

    # get AMI ID
    ami_id = system.name

    # define tags
    tags = [{'ResourceType': 'instance',
             'Tags': [{'Key': 'kraken-group', 'Value': '%d' % ag.id}]}]

    # prepare init script
    init_script = """#!/usr/bin/env bash
                     exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
                     wget -O agent {server_url}/install/agent
                     chmod a+x agent
                     ./agent install -s {server_url} -m {minio_addr} -c {clickhouse_addr}
                  """
    init_script = init_script.format(server_url=server_url, minio_addr=minio_addr, clickhouse_addr=clickhouse_addr)
    if aws.get('init_script', False):
        init_script += aws['init_script']

    # CPU Credits spec
    if aws.get('cpu_credits_unlimited', False):
        cpu_credits = 'unlimited'
    else:
        cpu_credits = 'standard'

    # spot instance
    instance_market_opts = {}
    if aws.get('spot_instance', False):
        instance_market_opts = {
            'MarketType': 'spot',
        }

    # collect all params
    params = dict(ImageId=ami_id,
                  MinCount=num,
                  MaxCount=num,
                  KeyName=key_name,
                  SecurityGroupIds=[sec_grp_id],
                  TagSpecifications=tags,
                  InstanceType=aws['instance_type'],
                  Monitoring={'Enabled': aws.get('monitoring', False)},
                  InstanceMarketOptions=instance_market_opts,
                  UserData=init_script)

    if 't2' in aws['instance_type'] or 't3' in aws['instance_type']:
        params['CreditSpecification'] = {'CpuCredits': cpu_credits}

    # create AWS EC2 instances
    instances = ec2_res.create_instances(**params)

    log.info('spawning new EC2 VMs for agents %s', instances)

    sys_id = system.id if system.executor == 'local' else 0

    now = utils.utcnow()
    for i in instances:
        try:
            i.wait_until_running()
        except Exception:
            log.exception('IGNORED EXCEPTION')
            continue
        i.load()
        name = '.'.join(i.public_dns_name.split('.')[:2])
        address = i.private_ip_address
        a = None
        params = dict(name=name,
                      address=address,
                      ip_address=i.public_ip_address,
                      extra_attrs=dict(system=sys_id, instance_id=i.id),
                      authorized=True,
                      last_seen=now)
        try:
            a = Agent(**params)
            db.session.commit()
        except Exception:
            db.session.rollback()
            a = Agent.query.filter_by(deleted=None, address=address).one_or_none()
            if a:
                for f, val in params.items():
                    setattr(a, f, val)
                db.session.commit()
            else:
                log.info('agent %s duplicated but cannot find it'. address)
                raise

        AgentAssignment(agent=a, agents_group=ag)
        db.session.commit()
        log.info('spawned new agent %s on EC2 instance %s', a, i)
