#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

Copyright (c) 2019 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""
__author__ = "Steven Mosher <stmosher@cisco.com>"
__copyright__ = "Copyright (c) 2019 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import os
import ipaddress
import random
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient
import azure.mgmt.network.models as network_models
import azure.mgmt.compute.models as compute_models
from multiprocessing import Process
from multiprocessing import Queue
from queue import Empty
from csr1000v import Router
from config import Settings


def generate_variables(rtr_list, g_vnet_types, g_instance_type, g_region, g_cluster, g_asn,
                       g_private_vnet_address_space, g_public_vnet_address_space, g_unique_prefix):
    """
    Input:
    rtr_list = list of integers specifying how many routers to deploy in VNET
    e.g., rtr_list = [1, 1, 2, 0, 0]

    g_vnet_types = list of the type of VNET to deploy
    e.g., g_vnet_types = ['hub', 'spoke', 'silb', 'vnet', 'vnet']

    g_instance_type = string of the instance type for all routers
    g_instance_type = 'Standard_DS3_v2'


    Output:
    Returns a list of variables dictionaries
    Each dictionary are variables for a VNET
    """
    settings = Settings()

    vars_list = list()
    public_cidr_net = ipaddress.IPv4Network(g_public_vnet_address_space)
    private_cidr_net = ipaddress.IPv4Network(g_private_vnet_address_space)
    dmvpn_net = ipaddress.IPv4Network(settings.dmvpn_address_space)

    counter = 0
    for i in range(len(g_vnet_types)):
        vars_list.append(dict(public_vnet_prefix=str(list(public_cidr_net.subnets(new_prefix=24))[i])))
        vars_list[i]['private_vnet_prefix'] = str(list(private_cidr_net.subnets(new_prefix=24))[i])
        vars_list[i]['g2_default_gateway'] = str(list(ipaddress.IPv4Network(vars_list[i]['private_vnet_prefix']).hosts())[0])
        vars_list[i]['dmvpn_address'] = []
        for j in range(rtr_list[i]):
            vars_list[i]['dmvpn_address'].append(str(list(dmvpn_net.hosts())[counter]))
            vars_list[i]['hostname'] = g_vnet_types[i] + str(j)
            counter += 1
        vars_list[i]['type'] = g_vnet_types[i]
        if g_vnet_types[i] == 'silb':
            vars_list[i]['lb_name'] = g_unique_prefix + str(i)
            vars_list[i]['availability_set_name'] = g_unique_prefix + str(i)
        vars_list[i]['instance_type'] = g_instance_type
        vars_list[i]['vnet_name'] = g_vnet_types[i] + str(i)
        vars_list[i]['random_prefix'] = g_unique_prefix + str(i)

        vars_list[i]['cloud_private_space'] = str(private_cidr_net.network_address)
        vars_list[i]['cloud_private_netmask'] = str(private_cidr_net.netmask)

        vars_list[i]['region'] = g_region
        vars_list[i]['tvpc_program_key'] = settings.tvpc_program_key
        vars_list[i]['cluster'] = g_cluster
        vars_list[i]['domain_name_label'] = g_unique_prefix + str(i)
        vars_list[i]['resource_group_name'] = g_unique_prefix + str(i)
        vars_list[i]['dmvpn_password'] = settings.dmvpn_password
        vars_list[i]['dmvpn_netmask'] = str(dmvpn_net.netmask)
        vars_list[i]['dmvpn_address_space'] = settings.dmvpn_address_space
        vars_list[i]['asn'] = g_asn
        vars_list[i]['username'] = settings.regions[region]['username']
        vars_list[i]['password'] = settings.regions[region]['password']
        vars_list[i]['wan_security_group_name'] = g_unique_prefix + str(i)
        random_id = g_unique_prefix + str(random.randrange(10000000, 100000000))
        vars_list[i]['storage_account_name'] = vars_list[i]['resource_group_name'] + random_id

    return vars_list


def create_vnet(results_queue, creds, subscription, vv):
    settings = Settings()
    hub_1_public = None
    hub_1_private = None

    resource_client = ResourceManagementClient(creds, subscription)
    compute_client = ComputeManagementClient(creds, subscription)
    storage_client = StorageManagementClient(creds, subscription)
    network_client = NetworkManagementClient(creds, subscription)

    # 1 Create Resource Group
    resg = resource_client.resource_groups.create_or_update(
        vv['resource_group_name'],
        {
            'location': vv['region']
        }
    )
    rg = resg.name

    # 2 Create WAN Network Security Group
    rule_ssh_in = network_models.SecurityRule(
        description='allow ssh in',
        protocol='TCP',
        source_port_range='*',
        destination_port_range='22',
        source_address_prefix='*',
        destination_address_prefix='*',  # Or to local CIDR
        access='Allow',
        priority=100,
        direction='Inbound',
        name='ssh-inbound'
    )
    rule_internet_key_exchange_in = network_models.SecurityRule(
        description='allow ike in',
        protocol='UDP',
        source_port_range='*',
        destination_port_range='500',
        source_address_prefix='*',
        destination_address_prefix='*',  # Or to local CIDR
        access='Allow',
        priority=110,
        direction='Inbound',
        name='ike-inbound'
    )
    rule_nat_t_in = network_models.SecurityRule(
        description='allow nat-t in',
        protocol='UDP',
        source_port_range='*',
        destination_port_range='4500',
        source_address_prefix='*',
        destination_address_prefix='*',  # Or to local CIDR
        access='Allow',
        priority=120,
        direction='Inbound',
        name='nat-t-inbound'
    )
    wan_ipsec_nsg_params = network_models.NetworkSecurityGroup(
        location=vv['region'], security_rules=[rule_ssh_in, rule_internet_key_exchange_in, rule_nat_t_in])
    nsg_creation = network_client.network_security_groups.create_or_update(rg, vv['wan_security_group_name'],
                                                                           wan_ipsec_nsg_params)
    wan_ipsec_nsg = network_client.network_security_groups.get(vv['resource_group_name'], vv['wan_security_group_name'])

    # Create Private Network Security Group
    all_in = network_models.SecurityRule(
        description='allow all traffic',
        protocol='*',
        source_port_range='*',
        destination_port_range='*',
        source_address_prefix='*',
        destination_address_prefix='*',
        access='Allow',
        priority=100,
        direction='Inbound',
        name='All'
    )
    open_nsg_params = network_models.NetworkSecurityGroup(
        location=vv['region'], security_rules=[all_in])
    open_nsg_creation = network_client.network_security_groups.create_or_update(rg, 'open_nsg',
                                                                                open_nsg_params)
    open_nsg = network_client.network_security_groups.get(vv['resource_group_name'], 'open_nsg')

    # 3 Create a VNET
    address_space_model = network_models.AddressSpace(
        address_prefixes=[vv['public_vnet_prefix'],
                          vv['private_vnet_prefix']]
    )
    if vv['type'] == 'silb':
        vnet_model = network_models.VirtualNetwork(
            location=vv['region'],
            tags={vv['tvpc_program_key']: vv['cluster'], 'tvpc_silb_vnet': 'True'},
            address_space=address_space_model,
        )
    elif vv['type'] == 'vnet':
        vnet_model = network_models.VirtualNetwork(
            location=vv['region'],
            tags={vv['tvpc_program_key']: vv['cluster']},
            address_space=address_space_model,
        )
    else:
        vnet_model = network_models.VirtualNetwork(
            location=vv['region'],
            address_space=address_space_model,
        )

    result_object_vnet_creation = network_client.virtual_networks.create_or_update(
        resource_group_name=vv['resource_group_name'],
        virtual_network_name=vv['vnet_name'],
        parameters=vnet_model
    )

    result_object_vnet_creation.wait()

    # 4 Create Routes
    default_route = network_models.Route(
        address_prefix='0.0.0.0/0',
        next_hop_type='Internet',
        name='default_route')

    private_subnet_route = network_models.Route(
        address_prefix=vv['private_vnet_prefix'],
        next_hop_type='VnetLocal',
        name='private_subnet_route')

    # 5 Create Route Tables
    wan_route_table_params = network_models.RouteTable(
        location=vv['region'],
        routes=[default_route, private_subnet_route]
    )
    result_object_route_table_wan_creation = network_client.route_tables.create_or_update(vv['resource_group_name'],
                                                                                  'wan_route_table',
                                                                                  wan_route_table_params)
    result_object_route_table_wan_creation.wait()
    wan_route_table = result_object_route_table_wan_creation.result()

    private_route_table_params = network_models.RouteTable(
        location=vv['region'],
        routes=[private_subnet_route]
    )
    result_object_route_table_private_creation = network_client.route_tables.create_or_update(vv['resource_group_name'],
                                                                                      'private_route_table',
                                                                                      private_route_table_params)
    result_object_route_table_private_creation.wait()
    private_route_table = result_object_route_table_private_creation.result()

    # 6 Create Subnets
    result_object_subnet_creation = network_client.subnets.create_or_update(
        resource_group_name=vv['resource_group_name'],
        virtual_network_name=vv['vnet_name'],
        subnet_name='TVPC_WAN_Subnet',
        subnet_parameters=network_models.Subnet(address_prefix=vv['public_vnet_prefix'],
                                                network_security_group=wan_ipsec_nsg,
                                                route_table=wan_route_table)
    )
    subnet_wan = result_object_subnet_creation.result()

    result_object_subnet_creation = network_client.subnets.create_or_update(
        resource_group_name=vv['resource_group_name'],
        virtual_network_name=vv['vnet_name'],
        subnet_name='TVPC_Private_Subnet',
        subnet_parameters=network_models.Subnet(address_prefix=vv['private_vnet_prefix'],
                                                route_table=private_route_table)
    )
    subnet_private = result_object_subnet_creation.result()

    # 7 Create Storage Account
    storage_result_object_operation = storage_client.storage_accounts.create(
        vv['resource_group_name'],
        vv['storage_account_name'],
        {
            'sku': {'name': 'standard_lrs'},
            'kind': 'storage',
            'location': vv['region']
        }
    )
    storage_result_object_operation.wait()

    # 8 Create an Availability Set
    if vv['type'] == 'silb':
        av_sku_params = compute_models.Sku(
            name='Aligned'
        )
        availability_set_parameters = compute_models.AvailabilitySet(
            location=vv['region'],
            platform_update_domain_count=5,
            platform_fault_domain_count=2,
            sku=av_sku_params
        )

        avset = compute_client.availability_sets.create_or_update(rg, vv['availability_set_name'],
                                                                  availability_set_parameters)
        avset_return = compute_client.availability_sets.get(vv['resource_group_name'], vv['availability_set_name'])

    # 9 Create Load Balancer
    if vv['type'] == 'silb':
        load_balancer_name = 'SILB'
        fip_name = 'FIPdmvpn'
        bap_name = 'BAPdmvpn'
        probe_name = 'SSHhealthcheck'
        silb_rule_name = 'slball'

        def construct_fip_id(subscription_id):
            return ('/subscriptions/{}'
                    '/resourceGroups/{}'
                    '/providers/Microsoft.Network'
                    '/loadBalancers/{}'
                    '/frontendIPConfigurations/{}').format(
                subscription_id, vv['resource_group_name'], load_balancer_name, fip_name
            )

        def construct_bap_id(subscription_id):
            return ('/subscriptions/{}'
                    '/resourceGroups/{}'
                    '/providers/Microsoft.Network'
                    '/loadBalancers/{}'
                    '/backendAddressPools/{}').format(
                subscription_id, vv['resource_group_name'], load_balancer_name, bap_name
            )

        def construct_probe_id(subscription_id):
            return ('/subscriptions/{}'
                    '/resourceGroups/{}'
                    '/providers/Microsoft.Network'
                    '/loadBalancers/{}'
                    '/probes/{}').format(
                subscription_id, vv['resource_group_name'], load_balancer_name, probe_name
            )

        subnet_silb = network_client.subnets.get(vv['resource_group_name'], vv['vnet_name'], 'TVPC_Private_Subnet')

        front_ip_config = network_models.FrontendIPConfiguration(
            private_ip_allocation_method='Dynamic',
            subnet={'id': subnet_silb.id},
            name=fip_name,

        )

        back_pool = network_models.BackendAddressPool(
            name=bap_name
        )

        fipn = construct_fip_id(subscription_id)
        bapn = construct_bap_id(subscription_id)
        proben = construct_probe_id(subscription_id)
        silb_rules = network_models.LoadBalancingRule(
            frontend_ip_configuration={'id': fipn},
            backend_address_pool={'id': bapn},
            probe={'id': proben},
            protocol='All',
            load_distribution='Default',
            frontend_port=0,
            backend_port=0,
            idle_timeout_in_minutes=4,
            enable_floating_ip=True,
            enable_tcp_reset=False,
            disable_outbound_snat=True,
            name=silb_rule_name
        )

        silb_probes = network_models.Probe(
            protocol='Tcp',
            port=22,
            interval_in_seconds=5,
            number_of_probes=2,
            name=probe_name
        )

        silb_sku = network_models.LoadBalancerSku(
            name='Standard'
        )
        silb_model = network_models.LoadBalancer(
            location=vv['region'],
            frontend_ip_configurations=[front_ip_config],
            backend_address_pools=[back_pool],
            load_balancing_rules=[silb_rules],
            probes=[silb_probes],
            sku=silb_sku,
            tags={vv['tvpc_program_key']: vv['cluster']},
        )

        lb_result_object_creation = network_client.load_balancers.create_or_update(
            resource_group_name=vv['resource_group_name'],
            load_balancer_name=load_balancer_name,
            parameters=silb_model
        )

        lb_info = lb_result_object_creation.result()
        bap_info = network_client.load_balancer_backend_address_pools.get(vv['resource_group_name'],
                                                                          load_balancer_name,
                                                                          bap_name)
    router_counter = 0
    for r in vv['dmvpn_address']:
        vv['router_counter'] = str(router_counter)
        vv['dmvpn_address_router'] = vv['dmvpn_address'][router_counter]
        # 9 Create PublicIP
        address_sku = network_models.PublicIPAddressSku(
            name='Standard'
        )
        public_ip_address_parameters = network_models.PublicIPAddress(
            location=vv['region'],
            public_ip_allocation_method='Static',
            sku=address_sku)
        pip_name = 'pip_' + str(router_counter)
        result_object_public_ip_creation = network_client.public_ip_addresses.create_or_update(
            vv['resource_group_name'], pip_name, public_ip_address_parameters)
        result_object_public_ip_creation.wait()
        public_ip_info = result_object_public_ip_creation.result()

        # 10 Create NICs
        nic_0_name = 'CSR_' + str(router_counter) + '_nic_0'
        nic_0_config = network_models.IPConfiguration(
            subnet=subnet_wan,
            name=nic_0_name,
            private_ip_allocation_method=network_models.IPAllocationMethod.dynamic,
            public_ip_address=public_ip_info
        )
        nic_0_parameters = network_models.NetworkInterface(
            location=vv['region'],
            network_security_group=wan_ipsec_nsg,
            enable_accelerated_networking=True,
            ip_configurations=[nic_0_config],
            primary=True,
            enable_ip_forwarding=False  # False
        )
        result_object_nic_0_create = network_client.network_interfaces.create_or_update(
            vv['resource_group_name'], nic_0_name, nic_0_parameters)
        result_object_nic_0_create.wait()
        nic_0 = result_object_nic_0_create.result()
        nic_0.primary = True  # This is a bug. The primary key is always None after interface create or update
        if vv['type'] == 'silb':
            nic_1_name = 'CSR_' + str(router_counter) + '_nic_1'
            result_object_nic_1_create = network_client.network_interfaces.create_or_update(
                vv['resource_group_name'],
                nic_1_name,
                {
                    'location': vv['region'],
                    'network_security_group': open_nsg,
                    'enable_accelerated_networking': True,
                    'enable_ip_forwarding': True,
                    'primary': False,
                    'ip_configurations': [{
                        'name': 'some_config_name',
                        'subnet': {
                            'id': subnet_silb.id
                        },
                        'private_ip_allocation_method': network_models.IPAllocationMethod.dynamic,
                        'load_balancer_backend_address_pools': [{
                            'id': bap_info.id
                        }]
                    }]
                }
            )
            result_object_nic_1_create.wait()
            nic_1 = result_object_nic_1_create.result()
            nic_1.primary = False  # This is a bug. The primary key is always None after interface create or update

        else:
            nic_1_name = 'CSR_' + str(router_counter) + '_nic_1'
            nic_1_config = network_models.IPConfiguration(
                subnet=subnet_private,
                name=nic_1_name,
                private_ip_allocation_method=network_models.IPAllocationMethod.dynamic
            )
            nic_1_parameters = network_models.NetworkInterface(
                location=vv['region'],
                network_security_group=wan_ipsec_nsg,
                enable_accelerated_networking=True,
                ip_configurations=[nic_1_config],
                primary=False,
                enable_ip_forwarding=True)
            result_object_nic_1_create = network_client.network_interfaces.create_or_update(
                vv['resource_group_name'], nic_1_name, nic_1_parameters)
            result_object_nic_1_create.wait()
            nic_1 = result_object_nic_1_create.result()
            nic_1.primary = False  # This is a bug. The primary key is always None after interface create or update

        # 11 Create VM
        computer_name = vv['hostname'] + str(router_counter)
        os_profile = compute_models.OSProfile(
            computer_name=computer_name,
            admin_username=vv['username'],
            admin_password=vv['password']
        )

        hardware_profile = compute_models.HardwareProfile(
            vm_size=vv['instance_type']
        )

        storage_profile = compute_models.StorageProfile(
            image_reference=compute_models.ImageReference(
                publisher='cisco',
                offer='cisco-csr-1000v',
                sku='16_10-byol',
                version='latest')
        )
        network_profile = compute_models.NetworkProfile(
            network_interfaces=[nic_0, nic_1]
        )
        image_plan = compute_models.Plan(
            name='16_10-byol',
            publisher='cisco',
            product='cisco-csr-1000v'
        )
        if vv['type'] == 'silb':
            vm_profile = compute_models.VirtualMachine(
                location=vv['region'],
                os_profile=os_profile,
                plan=image_plan,
                hardware_profile=hardware_profile,
                storage_profile=storage_profile,
                network_profile=network_profile,
                availability_set={'id': avset_return.id}

            )
        else:
            vm_profile = compute_models.VirtualMachine(
                location=vv['region'],
                os_profile=os_profile,
                plan=image_plan,
                hardware_profile=hardware_profile,
                storage_profile=storage_profile,
                network_profile=network_profile
            )

        result_object_vm_creation = compute_client.virtual_machines.create_or_update(vv['resource_group_name'],
                                                                                     computer_name, vm_profile)
        result_object_vm_creation.wait()
        vm_result = result_object_vm_creation.result()

        # Get IP address
        result = network_client.public_ip_addresses.get(rg, public_ip_info.name)
        public_ip = result.ip_address
        vv['public_ip'] = public_ip
        # If DMVPN hub, save info
        if vv['type'] == 'hub':
            hub_1_public = public_ip
            hub_1_private = vv['dmvpn_address_router']

        router = Router(vv['public_ip'], vv['username'], vv['password'], vv['region'], vv['instance_type'],
                        settings.instance_types[vv['instance_type']])
        if not router.initial_check_responsive():
            print('router unresponsive')
        if settings.regions[vv['region']]['smart_licensing'] == 'True':
            if not router.register():
                print('router unable to register with smart licensing')

        config = router.render_config_from_template(template_name='templates/baseline.j2', variables_dict=vv)

        # want an exception if configuration result is not true
        if not router.configure_router(config):
            print('unable to configure router')
        if vv['type'] == 'hub':
            config = router.render_config_from_template(template_name='templates/dmvpn_hub.j2', variables_dict=vv)
            if not router.configure_router(config):
                print('unable to configure router')
        elif vv['type'] == 'spoke':
            config = router.render_config_from_template(template_name='templates/dmvpn_spoke.j2', variables_dict=vv)
            if not router.configure_router(config):
                print('unable to configure router')
        elif vv['type'] == 'silb':
            config = router.render_config_from_template(template_name='templates/dmvpn_spoke_silb.j2',
                                                        variables_dict=vv)
            if not router.configure_router(config):
                print('unable to configure router')
        elif vv['type'] == 'vnet':
            config = router.render_config_from_template(template_name='templates/app_vnet.j2', variables_dict=vv)
            if not router.configure_router(config):
                print('unable to configure router')
        if not router.configure_router(['end', 'event  manager run 10interface']):
            print('unable to configure 10 gigabitethernet interface')
        router_counter += 1

    # Tag SILB VNET with SILB private IP
    if vv['type'] == 'silb':
        lb_info = network_client.load_balancers.get(vv['resource_group_name'], load_balancer_name)
        silb_private_ip = lb_info.frontend_ip_configurations[0].private_ip_address

        vnet = network_client.virtual_networks.get(vv['resource_group_name'], vv['vnet_name'])
        vnet.tags.update({'tvpc_silb_private_address': silb_private_ip})
        network_client.virtual_networks.create_or_update(vv['resource_group_name'], vv['vnet_name'], vnet)

    results_queue.put({'hub_1_public': hub_1_public, 'hub_1_private': hub_1_private})


def create_tasks(req_queue, num_processes, vnet_vars):
    """
         The request_queue is populated the router objects
    """
    for i in vnet_vars:
        req_queue.put(i)
    for i in range(num_processes):
        req_queue.put('DONE')


def work(req_queue, results_queue, creds, subscription):
    """
        This is the target function for each process.  It repeatedly grabs from the request_queue until it grabs the
        value "DONE" and then it terminates the work loop.
    """
    while True:
        try:
            val = req_queue.get(timeout=300)
            if val == 'DONE':
                break
            else:
                results_queue.put(create_vnet(results_queue, creds, subscription, val))
        except TimeoutError:
            break


def collect_results(results_queue):
    results = []
    while True:
        try:
            results_element = results_queue.get(block=False)
            if results_element is not None:
                results.append(results_element)
        except Empty:
            break
    return results


def create_hub_vnet(c_subscription_id, c_credentials, c_vnet_variables):
    # Create Hub
    req_queue = Queue()
    results_queue = Queue()
    num_processes = len(c_vnet_variables[:1])
    processes = []

    create_tasks(req_queue, num_processes, c_vnet_variables[:1])

    for i in range(num_processes):
        p = Process(target=work, args=(req_queue, results_queue, c_credentials, c_subscription_id))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    return collect_results(results_queue)


def create_remaining_vnets(c_subscription_id, c_credentials, c_vnet_variables):
    # Deploy the rest of the VNETs
    req_queue = Queue()
    results_queue = Queue()
    num_processes = len(c_vnet_variables[1:])
    processes = []

    create_tasks(req_queue, num_processes, c_vnet_variables[1:])

    for i in range(num_processes):
        p = Process(target=work, args=(req_queue, results_queue, c_credentials, c_subscription_id))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    return collect_results(results_queue)


if __name__ == '__main__':
    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
    credentials = ServicePrincipalCredentials(
        client_id=os.environ.get('AZURE_CLIENT_ID'),
        secret=os.environ.get('AZURE_CLIENT_SECRET'),
        tenant=os.environ.get('AZURE_TENANT_ID')
    )

    region = 'westus'
    instance_type = 'Standard_DS3_v2'
    cluster = 'dev'
    asn = '65535'
    private_vnet_address_space = '10.100.0.0/21'
    public_vnet_address_space = '172.16.0.0/21'
    unique_prefix = 'sm10'

    router_list = [1, 1, 1, 2]
    types = ['hub', 'vnet', 'vnet', 'silb']

    vnet_variables = generate_variables(router_list, types, instance_type, region, cluster, asn,
                                        private_vnet_address_space, public_vnet_address_space, unique_prefix)

    # Build Hub First to get DMVPN and BGP info
    results1 = create_hub_vnet(subscription_id, credentials, vnet_variables)

    # Add Hub info to other VNET variable dictionaries
    for j in vnet_variables:
        j['hub_1_public'] = results1[0]['hub_1_public']
        j['hub_1_private'] = results1[0]['hub_1_private']

    # Create the rest of the VNETs in parallel
    results2 = create_remaining_vnets(subscription_id, credentials, vnet_variables)
