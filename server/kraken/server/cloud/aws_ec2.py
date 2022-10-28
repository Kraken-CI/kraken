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
import datetime

import pytz
import requests
from sqlalchemy.orm.attributes import flag_modified

# AWS
import boto3
import botocore

from ..models import db
from .. import utils
from .aws import login_to_aws
from .common import _create_agent


log = logging.getLogger(__name__)


def create_vms(ag, system, num,
               server_url, clickhouse_addr):
    credential = login_to_aws()
    if not credential:
        return

    _, aws = ag.get_deployment()

    region = aws['region']
    ec2 = boto3.client("ec2", region_name=region, **credential)
    ec2_res = boto3.resource('ec2', region_name=region, **credential)

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
                     wget -O agent {server_url}/bk/install/agent
                     chmod a+x agent
                     ./agent install -s {server_url} -c {clickhouse_addr} --system-id {system_id}
                  """
    init_script = init_script.format(server_url=server_url, clickhouse_addr=clickhouse_addr,
                                     system_id=system.id)
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

    # prepare disk size if provided
    disk_size = aws.get('disk_size', 0)
    if disk_size:
        params['BlockDeviceMappings'] = [{
            'DeviceName': '/dev/sda1',
            'Ebs': {
                'VolumeSize': disk_size
            }
        }]

    # create AWS EC2 instances
    instances = ec2_res.create_instances(**params)

    log.info('spawning new EC2 VMs for agents %s', instances)

    sys_id = system.id if system.executor == 'local' else 0

    print('instances', instances)
    for i in instances:
        print('iii', i)

        try:
            i.wait_until_running()
        except Exception:
            log.exception('IGNORED EXCEPTION')
            continue
        i.load()
        name = '.'.join(i.public_dns_name.split('.')[:2])
        address = i.private_ip_address
        params = dict(name=name,
                      address=address,
                      ip_address=i.public_ip_address,
                      extra_attrs=dict(system=sys_id, instance_id=i.id))
        a = _create_agent(params, ag)
        log.info('spawned new agent %s on EC2 instance %s', a, i)


def destroy_vm(ag, agent):  # pylint: disable=unused-argument
    credential = login_to_aws()
    if not credential:
        return

    _, depl = ag.get_deployment()

    region = depl['region']
    ec2 = boto3.resource('ec2', region_name=region, **credential)

    instance_id = agent.extra_attrs['instance_id']
    log.info('terminate ec2 vm %s', instance_id)
    try:
        i = ec2.Instance(instance_id)
        i.terminate()
    except Exception:
        log.exception('IGNORED EXCEPTION')


def vm_exists(ag, agent):
    credential = login_to_aws()
    if not credential:
        raise Exception('wrong aws credential')

    _, depl = ag.get_deployment()

    region = depl['region']
    ec2 = boto3.resource('ec2', region_name=region, **credential)

    instance_id = agent.extra_attrs['instance_id']
    try:
        # try to get instance, if missing then raised exception will cause return False
        i = ec2.Instance(instance_id)
        i.state  # pylint: disable=pointless-statement
        if i.state['Name'] == 'terminated':
            # if instance exists theb raising an exception and it will cause return False
            raise Exception('terminated')
    except Exception:
        return False

    return True


def cleanup_dangling_vms(ag):
    credential = login_to_aws()
    if not credential:
        return 0, 0, 0, 0, 0

    _, depl = ag.get_deployment()

    region = depl['region']
    ec2 = boto3.resource('ec2', region_name=region, **credential)

    now = utils.utcnow()

    try:
        vms = ec2.instances.filter(Filters=[{'Name': 'tag:kraken-group', 'Values': ['%d' % ag.id]}])
        vms = list(vms)
    except Exception:
        log.exception('IGNORED EXCEPTION')
        return 0, 0, 0, 0, 0

    instances = 0
    terminated_instances = 0
    assigned_instances = 0
    orphaned_instances = 0
    orphaned_terminated_instances = 0

    for vm in vms:
        instances += 1
        # if terminated then skip it
        if vm.state['Name'] == 'terminated':
            terminated_instances += 1
            continue

        # if assigned to some agent then skip it
        assigned = False
        for aa in ag.agents:
            agent = aa.agent
            if agent.extra_attrs and 'instance_id' in agent.extra_attrs and agent.extra_attrs['instance_id'] == vm.id:
                assigned = True
                break
        if assigned:
            assigned_instances += 1
            continue

        # instances have to be old enough to avoid race condition with
        # case when instances are being created but not yet assigned to agents
        lt = vm.launch_time.replace(tzinfo=pytz.utc)
        if now - lt < datetime.timedelta(minutes=10):
            continue

        # the instance is not terminated, not assigned, old enough
        # so delete it as it seems to be a lost instance
        log.info('terminating lost aws ec2 instance %s', vm.id)
        orphaned_instances += 1
        try:
            vm.terminate()
        except Exception:
            log.exception('IGNORED EXCEPTION')

        orphaned_terminated_instances += 1

    return instances, terminated_instances, assigned_instances, orphaned_instances, orphaned_terminated_instances
