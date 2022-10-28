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

import time
import logging

# AWS
import boto3

from .aws import login_to_aws
from .common import _create_agent


log = logging.getLogger(__name__)


# AWS ECS FARGATE #############################################################

def create_fargate_tasks(ag, system, num,
                         server_url, clickhouse_addr):
    credential = login_to_aws()
    if not credential:
        return

    _, aws = ag.get_deployment()

    region = aws['region']
    ec2 = boto3.client("ec2", region_name=region, **credential)
    ecs = boto3.client('ecs', region_name=region, **credential)

    system_norm = system.name.replace(':', '_').replace('/', '_').replace('.', '_')
    task_def_name = 'kraken-agent-1-%s' % system_norm

    # if there is no task definition yet then create one
    response = ecs.list_task_definitions(familyPrefix=task_def_name)
    if len(response['taskDefinitionArns']) == 0:
        ecs.register_task_definition(
            family=task_def_name,
            containerDefinitions=[{
                "name": "kraken-agent",
                "image": system.name,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/kraken-agent-definition",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs"
                    }
                },
            }],
            requiresCompatibilities=['FARGATE'],
            memory="512",
            cpu="256",
            networkMode="awsvpc",
            executionRoleArn="arn:aws:iam::214272040963:role/ecsTaskExecutionRole",
        )

    # prepare command for container
    cmd = 'apt-get update && apt-get install -y --no-install-recommends ca-certificates sudo wget python3'
    cmd += ' && mkdir -p /opt/kraken'
    cmd += ' && wget -O /opt/kraken/kkagent {server_url}/bk/install/agent'
    cmd += ' && wget -O /opt/kraken/kktool {server_url}/bk/install/tool'
    cmd += ' && chmod a+x /opt/kraken/kkagent /opt/kraken/kktool'
    cmd += ' && mkdir -p /tmp/kk-jobs'
    cmd += ' && /opt/kraken/kkagent run -d /tmp/kk-jobs -s {server_url} -c {clickhouse_addr}'
    cmd += ' --system-id {system_id} --one-job'
    cmd = cmd.format(server_url=server_url, clickhouse_addr=clickhouse_addr,
                     system_id=system.id)

    cluster = aws['cluster']
    subnets = aws['subnets'].split(',')
    security_groups = aws['security_groups'].split(',')

    response = ecs.run_task(
        taskDefinition=task_def_name,
        count=num,
        cluster=cluster,
        launchType="FARGATE",
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': subnets,
                'securityGroups': security_groups,
                'assignPublicIp': 'ENABLED'
            }
        },
        overrides={
            'containerOverrides': [{
                'name': 'kraken-agent',
                'command': [
                    'bash', '-c', cmd
                ],
                'environment': [
                    {'name': 'KRAKEN_SERVER_ADDR', 'value': server_url},
                    {'name': 'KRAKEN_CLICKHOUSE_ADDR', 'value': clickhouse_addr},
                ],
                #'cpu': 123,
                #'memory': 123,
                #'memoryReservation': 123,
            }],
            #'cpu': 'string',
            #'memory': 'string',
        }
    )

    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        log.warning('some problem occured')
        log.warning(response)
        return

    all_tasks = [t['taskArn'] for t in response['tasks']]
    tasks_ready = []
    tasks_not_ready = all_tasks[:]
    erred_task = None
    while len(tasks_not_ready) > 0 and not erred_task:
        resp = ecs.describe_tasks(cluster=cluster,
                                  tasks=tasks_not_ready)
        tasks_ready = []
        tasks_not_ready = []
        for task in resp['tasks']:
            if task['lastStatus'] == 'STOPPED':
                erred_task = task
                break
            if task['lastStatus'] != 'RUNNING':
                tasks_not_ready.append(task['taskArn'])
                continue
            eni = None
            for field in task['attachments'][0]['details']:
                if field['name'] == 'networkInterfaceId':
                    eni = field['value']
            if not eni:
                tasks_not_ready.append(task['taskArn'])
                continue
            iface_resp = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni])
            priv_ip = iface_resp['NetworkInterfaces'][0]['PrivateIpAddress']
            pub_dns = iface_resp['NetworkInterfaces'][0]['Association']['PublicDnsName']
            pub_ip = iface_resp['NetworkInterfaces'][0]['Association']['PublicIp']
            name = '.'.join(pub_dns.split('.')[:2])
            tasks_ready.append(dict(task_arn=task['taskArn'],
                                    name=name,
                                    address=priv_ip,
                                    ip_address=pub_ip))
        if tasks_not_ready:
            time.sleep(2)

    if erred_task:
        msg = erred_task['containers'][0]['reason']
        log.warning('problem with starting task %s: %s', erred_task['taskArn'], msg)
        # stop all tasks
        for t in all_tasks:
            try:
                ecs.stop_task(cluster=cluster,
                              task=t,
                              reason='stopping other tasks due to an error')
            except Exception:
                log.exception('IGNORED EXCEPTION')

    for task in tasks_ready:
        address = task['address']
        params = dict(name=task['name'],
                      address=address,
                      ip_address=task['ip_address'],
                      extra_attrs=dict(system=0, task_arn=task['task_arn']))
        a = _create_agent(params, ag)
        log.info('spawned new agent %s on ECS Fargate task %s', a, task)


def destroy_fargate_task(ag, agent):  # pylint: disable=unused-argument
    credential = login_to_aws()
    if not credential:
        return

    _, depl = ag.get_deployment()

    region = depl['region']
    ecs = boto3.client('ecs', region_name=region, **credential)

    task_arn = agent.extra_attrs['task_arn']
    log.info('terminate ecs task %s', task_arn)
    try:
        ecs.stop_task(cluster=depl['cluster'],
                      task=task_arn,
                      reason='stopping task that completed the job')
    except Exception:
        log.exception('IGNORED EXCEPTION')
