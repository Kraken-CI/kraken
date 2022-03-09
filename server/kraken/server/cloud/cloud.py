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

from .. import consts
from . import aws_ec2
from . import aws_ecs
from . import azure
from . import k8s


log = logging.getLogger(__name__)


def create_machines(ag, system, num,
                    server_url, clickhouse_addr):
    method, _ = ag.get_deployment()
    if method == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
        aws_ec2.create_vms(ag, system, num,
                           server_url, clickhouse_addr)

    elif method == consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE:
        aws_ecs.create_fargate_tasks(ag, system, num,
                                     server_url, clickhouse_addr)

    elif method == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
        azure.create_vms(ag, system, num,
                         server_url, clickhouse_addr)

    elif method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
        k8s.create_pods(ag, system, num,
                        server_url, clickhouse_addr)

    else:
        raise NotImplementedError('deployment method %s not supported' % method)


def destroy_machine(ag, agent):
    method, _ = ag.get_deployment()
    if method == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
        aws_ec2.destroy_vm(ag, agent)
    elif method == consts.AGENT_DEPLOYMENT_METHOD_AWS_ECS_FARGATE:
        aws_ecs.destroy_fargate_task(ag, agent)
    elif method == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
        azure.destroy_vm(ag, agent)
    elif method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
        k8s.destroy_pod(ag, agent)

    else:
        raise NotImplementedError('deployment method %s not supported' % method)


def check_if_machine_exists(ag, agent):
    method, _ = ag.get_deployment()
    if method == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
        return aws_ec2.vm_exists(ag, agent)
    if method == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
        return azure.vm_exists(ag, agent)
    if method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
        return k8s.pod_exists(ag, agent)
    raise NotImplementedError('deployment method %s not supported' % method)


def cleanup_dangling_machines(ag):
    method, _ = ag.get_deployment()
    if method == consts.AGENT_DEPLOYMENT_METHOD_AWS_EC2:
        return aws_ec2.cleanup_dangling_vms(ag)
    if method == consts.AGENT_DEPLOYMENT_METHOD_AZURE_VM:
        return azure.cleanup_dangling_vms(ag)
    if method == consts.AGENT_DEPLOYMENT_METHOD_K8S:
        return k8s.cleanup_dangling_pods(ag)
    return 0, 0, 0, 0, 0


#if __name__ == '__main__':
#    sys_img = 'ubuntu:20.04'
#    #sys_img = 'public.ecr.aws/kraken-ci/kkagent:0.627'
#    main(sys_img, 'http://89.65.138.0:8080', '89.65.138.0:6363', '89.65.138.0:9999', '89.65.138.0:9001')
