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
import random
import logging
import datetime

# AZURE
import azure
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import SecurityRuleAccess, SecurityRuleDirection, SecurityRuleProtocol
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.monitor import MonitorManagementClient

from .. import utils
from .. import dbutils
from ..models import get_setting
from .common import _create_agent


log = logging.getLogger(__name__)


# AZURE VM ####################################################################

def check_azure_settings():
    subscription_id = get_setting('cloud', 'azure_subscription_id')
    if not subscription_id:
        return 'Azure Subscription ID is empty'
    # TODO
    # if len(access_key) < 16:
    #     return 'AWS access key is too short'
    # if len(access_key) > 128:
    #     return 'AWS access key is too long'

    tenant_id = get_setting('cloud', 'azure_tenant_id')
    if not tenant_id:
        return 'Azure Tenant ID is empty'

    client_id = get_setting('cloud', 'azure_client_id')
    if not client_id:
        return 'Azure Client ID is empty'

    client_secret = get_setting('cloud', 'azure_client_secret')
    if not client_secret:
        return 'Azure Client Secret is empty'

    try:
        credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        subscription_client = SubscriptionClient(credential)
        subscription_client.subscriptions.list_locations(subscription_id)
    except Exception as ex:
        return str(ex)

    return 'ok'


def login_to_azure():
    subscription_id = get_setting('cloud', 'azure_subscription_id')
    tenant_id = get_setting('cloud', 'azure_tenant_id')
    client_id = get_setting('cloud', 'azure_client_id')
    client_secret = get_setting('cloud', 'azure_client_secret')
    settings = ['subscription_id', 'tenant_id', 'client_id', 'client_secret']
    for s in settings:
        val = locals()[s]
        if not val:
            log.error('Azure %s is empty, please set it in global cloud settings', s)
            return None, None

    credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
    return credential, subscription_id


def _create_azure_vm(ag, system,
                     server_url, clickhouse_addr,
                     credential, subscription_id):
    instance_id = str(random.randrange(9999999999))

    _, depl = ag.get_deployment()

    location = depl['location']
    vm_size = depl['vm_size']

    sys_parts = system.name.split(':')
    if len(sys_parts) != 4:
        log.warning('incorrect system image name %s, Azure image name should have form <publisher>:<offer>:<sku>:<version>',
                    system.name)
        return

    log.info("Provisioning a virtual machine...some operations might take a minute or two.")

    # Step 1: Provision a resource group

    # Obtain the management object for resources, using the credential from the CLI login.
    resource_client = ResourceManagementClient(credential, subscription_id)

    # Provision the resource groups.
    global_rg = "kraken-rg"
    rg_result = resource_client.resource_groups.create_or_update(
        global_rg,
        {
            "location": location
        }
    )
    log.info("Provisioned global resource group %s in the %s region",
             rg_result.name, rg_result.location)

    group_rg = "kraken-%d-rg" % ag.id
    rg_result = resource_client.resource_groups.create_or_update(
        group_rg,
        {
            "location": location
        }
    )
    log.info("Provisioned resource group %s in the %s region",
             rg_result.name, rg_result.location)


    # For details on the previous code, see Example: Provision a resource group
    # at https://docs.microsoft.com/azure/developer/python/azure-sdk-example-resource-group


    # Step 2: provision a virtual network

    # A virtual machine requires a network interface client (NIC). A NIC requires
    # a virtual network and subnet along with an IP address. Therefore we must provision
    # these downstream components first, then provision the NIC, after which we
    # can provision the VM.

    # Network and IP address names
    vnet_name = "kraken-vnet"
    subnet_name = "kraken-subnet"

    ip_config_name = "kraken-%s-ip-config" % instance_id
    ip_name = "kraken-%s-ip" % instance_id
    nic_name = "kraken-%s-nic" % instance_id
    vm_name = "kraken-agent-%s-vm" % instance_id

    # Obtain the management object for networks
    network_client = NetworkManagementClient(credential, subscription_id)

    # if VNET exists then use it, otherwise create new one
    try:
        vnet_result = network_client.virtual_networks.get(global_rg, vnet_name)
    except azure.core.exceptions.ResourceNotFoundError:
        # Provision the virtual network and wait for completion
        poller = network_client.virtual_networks.begin_create_or_update(
            global_rg,
            vnet_name,
            {
                "location": location,
                "address_space": {
                    "address_prefixes": ["10.0.0.0/16"]
                }
            })

        vnet_result = poller.result()

    log.info("Provisioned virtual network %s with address prefixes %s",
             vnet_result.name, vnet_result.address_space.address_prefixes)

    #########
    security_group_name = 'kraken-nsg'
    try:
        security_group = network_client.network_security_groups.get(global_rg, security_group_name)
    except azure.core.exceptions.ResourceNotFoundError:
        #security_group_params = NetworkSecurityGroup(
        #    id="testnsg",
        #    location=self.location,
        #    tags={"name": security_group_name}
        #)
        poller = network_client.network_security_groups.begin_create_or_update(
            global_rg,
            security_group_name,
            {
                "location": location,
            }
        )
        security_group = poller.result()

    ssh_security_rule_name = 'kraken-ssh-rule'
    try:
        network_client.security_rules.get(global_rg, security_group_name, ssh_security_rule_name)
    except azure.core.exceptions.ResourceNotFoundError:
        poller = network_client.security_rules.begin_create_or_update(
            global_rg,
            security_group_name,
            ssh_security_rule_name,
            {
                'access': SecurityRuleAccess.allow,
                'description': 'SSH security rule',
                'destination_address_prefix': '*',
                'destination_port_range': '22',
                'direction': SecurityRuleDirection.inbound,
                'priority': 400,
                'protocol': SecurityRuleProtocol.tcp,
                'source_address_prefix': '*',  # TODO: change it to my_ip
                'source_port_range': '*',
            }
        )
        poller.result()
    #########

    # Step 3: Provision the subnet and wait for completion
    # if subnet exists then use it, otherwise create new one
    try:
        subnet_result = network_client.subnets.get(global_rg, vnet_name, subnet_name)
    except Exception:
        poller = network_client.subnets.begin_create_or_update(
            global_rg,
            vnet_name,
            subnet_name,
            {
                "address_prefix": "10.0.0.0/24",
            }
        )
        subnet_result = poller.result()

    log.info("Provisioned virtual subnet %s with address prefix %s",
             subnet_result.name, subnet_result.address_prefix)

    # Step 4: Provision an IP address and wait for completion
    poller = network_client.public_ip_addresses.begin_create_or_update(
        group_rg,
        ip_name,
        {
            "location": location,
            "sku": { "name": "Standard" },
            "public_ip_allocation_method": "Static",
            "public_ip_address_version" : "IPV4"
        }
    )
    ip_address_result = poller.result()

    log.info("Provisioned public IP address %s with address %s",
             ip_address_result.name, ip_address_result.ip_address)

    # Step 5: Provision the network interface client
    poller = network_client.network_interfaces.begin_create_or_update(
        group_rg,
        nic_name,
        {
            "location": location,
            "ip_configurations": [{
                "name": ip_config_name,
                "subnet": { "id": subnet_result.id },
                "public_ip_address": {"id": ip_address_result.id }
            }],
            "network_security_group": {"id": security_group.id }
        }
    )

    nic_result = poller.result()

    log.info("Provisioned network interface client %s", nic_result.name)

    # Step 6: Provision the virtual machine

    # Obtain the management object for virtual machines
    compute_client = ComputeManagementClient(credential, subscription_id)

    username = "kraken"
    password = "kraken123!"

    log.info("Provisioning virtual machine %s; this operation might take a few minutes.", vm_name)

    # Provision the VM specifying only minimal arguments, which defaults to an Ubuntu 18.04 VM
    # on a Standard DS1 v2 plan with a public IP address and a default virtual network/subnet.

    init_script = """#!/usr/bin/env bash
                     exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
                     wget -O agent {server_url}/bk/install/agent
                     chmod a+x agent
                     ./agent install -s {server_url} -c {clickhouse_addr} --system-id {system_id}
                  """
    init_script = init_script.format(server_url=server_url, clickhouse_addr=clickhouse_addr,
                                     system_id=system.id)

    poller = compute_client.virtual_machines.begin_create_or_update(
        group_rg,
        vm_name,
        {
            "location": location,
            "storage_profile": {
                "image_reference": {
                    "publisher": sys_parts[0],  # 'Canonical',
                    "offer": sys_parts[1],  # "0001-com-ubuntu-server-focal",
                    "sku": sys_parts[2],  # "20_04-lts",
                    "version": sys_parts[3]  # "latest"
                }
                #"image_reference": "Canonical:0001-com-ubuntu-server-focal:20_04-lts:20.04.202109080"
            },
            "hardware_profile": {
                "vm_size": vm_size
            },
            "os_profile": {
                "computer_name": vm_name,
                "admin_username": username,
                "admin_password": password,
            },
            "network_profile": {
                "network_interfaces": [{
                    "id": nic_result.id,
                }]
            },
            "user_data": base64.b64encode(init_script.encode('utf-8')).decode()
        }
    )

    vm_result = poller.result()

    log.info("Provisioned Azure virtual machine %s", vm_result.name)

    # VM params
    sys_id = system.id if system.executor == 'local' else 0
    address = nic_result.ip_configurations[0].private_ip_address
    params = dict(name=vm_name,
                  address=address,
                  ip_address=ip_address_result.ip_address,
                  extra_attrs=dict(
                      system=sys_id,
                      instance_id=instance_id))

    a = _create_agent(params, ag)
    log.info('spawned new agent %s on Azure VM instance %s at %s', a, vm_result.name, a.created)


def create_vms(ag, system, num,
               server_url, clickhouse_addr):

    # Acquire a credential object using service principal authentication.
    credential, subscription_id = login_to_azure()
    if not credential:
        return

    for _ in range(num):
        _create_azure_vm(ag, system,
                         server_url, clickhouse_addr,
                         credential, subscription_id)


def _destroy_azure_vm(rg, vm_name, cc, nc):
    # get instance id from vm name, name is as follows "kraken-agent-<instance_id>-vm"
    instance_id = vm_name[13:-3]

    try:
        vm = cc.virtual_machines.get(rg, vm_name)
        disk_name = vm.storage_profile.os_disk.name
        cc.virtual_machines.begin_delete(rg, vm_name).wait()
        cc.disks.begin_delete(rg, disk_name)
    except azure.core.exceptions.ResourceNotFoundError:
        log.info('azure vm %s already missing', vm_name)

    nic_name = "kraken-%s-nic" % instance_id
    try:
        nc.network_interfaces.begin_delete(rg, nic_name).wait()
    except azure.core.exceptions.ResourceNotFoundError:
        log.info('azure nic %s already missing', nic_name)

    # ip_config_name = "kraken-%s-ip-config" % instance_id
    ip_name = "kraken-%s-ip" % instance_id
    try:
        nc.public_ip_addresses.begin_delete(rg, ip_name).wait()
    except azure.core.exceptions.ResourceNotFoundError:
        log.info('azure ip %s already missing', ip_name)

    log.info('deleted azure vm: %s', vm_name)


def destroy_vm(ag, agent):  # pylint: disable=unused-argument
    instance_id = agent.extra_attrs['instance_id']
    vm_name = "kraken-agent-%s-vm" % instance_id
    rg = 'kraken-%d-rg' % ag.id

    log.info('deleting azure vm: %s', vm_name)

    # Acquire a credential object using service principal authentication.
    credential, subscription_id = login_to_azure()
    if not credential:
        return

    cc = ComputeManagementClient(credential, subscription_id)
    nc = NetworkManagementClient(credential, subscription_id)

    _destroy_azure_vm(rg, vm_name, cc, nc)


def vm_exists(ag, agent):
    instance_id = agent.extra_attrs['instance_id']
    ag = dbutils.find_cloud_assignment_group(agent)
    if not ag:
        return False
    rg = 'kraken-%d-rg' % ag.id
    vm_name = "kraken-agent-%s-vm" % instance_id

    credential, subscription_id = login_to_azure()
    if not credential:
        raise Exception('wrong azure credential')

    cc = ComputeManagementClient(credential, subscription_id)
    try:
        cc.virtual_machines.get(rg, vm_name)
    except azure.core.exceptions.ResourceNotFoundError:
        return False

    return True


def cleanup_dangling_vms(ag):  # pylint: disable=unused-argument
    credential, subscription_id = login_to_azure()
    if not credential:
        return 0, 0, 0, 0, 0

    cc = ComputeManagementClient(credential, subscription_id)
    mc = MonitorManagementClient(credential, subscription_id)
    nc = NetworkManagementClient(credential, subscription_id)

    rg = 'kraken-%d-rg' % ag.id
    now = utils.utcnow()

    try:
        vms = cc.virtual_machines.list(rg)
    except azure.core.exceptions.ResourceNotFoundError:
        return 0, 0, 0, 0, 0

    instances = 0
    terminated_instances = 0
    assigned_instances = 0
    orphaned_instances = 0
    orphaned_terminated_instances = 0

    for vm in vms:
        instances += 1

        # if vm is being deleted then skip it
        vm2 = cc.virtual_machines.instance_view(rg, vm.name)
        log.info('vm %s statuses:', vm.name)
        skip = False
        for s in vm2.statuses:
            log.info(s.code)
            if s.code == 'ProvisioningState/deleting':
                skip = True
                break
        if skip:
            continue

        # if assigned to some agent then skip it
        assigned = False
        for aa in ag.agents:
            agent = aa.agent
            if agent.extra_attrs and 'instance_id' in agent.extra_attrs:
                instance_id = agent.extra_attrs['instance_id']
                vm_name = "kraken-agent-%s-vm" % instance_id
                if vm_name == vm.name:
                    assigned = True
                    break
        if assigned:
            assigned_instances += 1
            continue

        # instances have to be old enough to avoid race condition with
        # case when instances are being created but not yet assigned to agents
        fltr = " and ".join([ "eventTimestamp ge '{}T00:00:00Z'".format(now.date()),
                              "resourceUri eq '%s'" % vm.id ])
        created_at = None
        for l in mc.activity_logs.list(filter=fltr, select="eventTimestamp"):
            created_at = l.event_timestamp
        if not created_at or now - created_at < datetime.timedelta(minutes=10):
            continue

        # the instance is not terminated, not assigned, old enough
        # so delete it as it seems to be a lost instance
        log.info('terminating lost azure vm instance %s', vm.name)
        orphaned_instances += 1
        try:
            _destroy_azure_vm(rg, vm.name, cc, nc)
        except Exception:
            log.exception('IGNORED EXCEPTION')

        orphaned_terminated_instances += 1

    return instances, terminated_instances, assigned_instances, orphaned_instances, orphaned_terminated_instances
