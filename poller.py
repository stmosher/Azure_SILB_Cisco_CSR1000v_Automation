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
from config import Settings
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient
import azure.mgmt.network.models as network_models
import logging
import gc
import time

if __name__ == '__main__':
    # logging info
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(handlers=[
        logging.FileHandler("{0}/{1}.log".format('./', 'azure_poller')),
        logging.StreamHandler()], format=FORMAT, level=logging.INFO)
    logger = logging.getLogger(__name__)

    while True:

        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        credentials = ServicePrincipalCredentials(
            client_id=os.environ.get('AZURE_CLIENT_ID'),
            secret=os.environ.get('AZURE_CLIENT_SECRET'),
            tenant=os.environ.get('AZURE_TENANT_ID')
        )
        resource_client = ResourceManagementClient(credentials, subscription_id)
        compute_client = ComputeManagementClient(credentials, subscription_id)
        storage_client = StorageManagementClient(credentials, subscription_id)
        network_client = NetworkManagementClient(credentials, subscription_id)

        """
        get all VNETS with the tvpc_program_key
        put all SILB VNET objects in tvpc_silb_vnets
        put all participating VNETs in tvpc_participants
        """
        settings = Settings()
        tvpc_silb_vnets = list()
        tvpc_participants = list()
        result_all = list()
        try:
            result_all = network_client.virtual_networks.list_all()
        except Exception as e:
            logger.warning("Unable to access Azure")
            logger.error("{}".format(e))

        try:
            result_all = network_client.virtual_networks.list_all()
        except Exception as e:
            logger.warning("Unable to access Azure")
            logger.error("{}".format(e))

        for i in result_all:
            try:
                if i.tags.get(settings.tvpc_program_key, False) and (i.tags.get('tvpc_silb_vnet') == 'True'):
                    tvpc_silb_vnets.append(i)
                elif i.tags.get(settings.tvpc_program_key, False):
                    tvpc_participants.append(i)
            except:
                continue

        """
        for all tvpc_participants
        if there is a cluster and region matching tvpc_silb_vnet
        check to see if peering is already established
        if so, remove the peer from the tvpc_silb_vnet object
        if not, create the peering and a default route to the appropriate SILB in the participating VNET
        """
        for s in tvpc_silb_vnets:
            """rg is a new attribute for resource group name"""
            temp = s.id.split('/')
            s.rg = temp[4]  # Create a resource group name attribute for SILB VNETs

        for i in tvpc_participants:
            peering_index = None  # Used later to remove peer from SILB VNET object
            i.partner = False  # After processing VNETs without SILB peer will have peering connections and rts removed
            temp = i.id.split('/')
            i.rg = temp[4]  # Create resource group name attribute for the participating VNETs
            for s in tvpc_silb_vnets:
                if (i.tags.get(settings.tvpc_program_key) == s.tags.get(settings.tvpc_program_key)) and (
                        i.location == s.location):
                    i.partner = True
                    # add statement for if i does not already have a peer with s
                    for x in s.virtual_network_peerings:
                        if x.remote_virtual_network.id == i.id:
                            peering_index = s.virtual_network_peerings.index(x)
                            break
                    if peering_index or peering_index == 0:
                        # remove the peering from the silb so the remaining aren't needed for removal
                        del s.virtual_network_peerings[peering_index]
                    else:
                        try:
                            # build and break
                            peer_model = network_models.VirtualNetworkPeering(
                                allow_virtual_network_access=True,
                                allow_forwarded_traffic=False,
                                allow_gateway_transit=False,
                                use_remote_gateways=False,
                                remote_virtual_network={'id': i.id})
                            # use the same peering name for both sides to simplify peering termination
                            name = s.name + 'to' + i.name
                            network_client.virtual_network_peerings.create_or_update(s.rg, s.name, name, peer_model)
                            # Create I to S
                            peer_model = network_models.VirtualNetworkPeering(
                                allow_virtual_network_access=True,
                                allow_forwarded_traffic=True,
                                allow_gateway_transit=False,
                                use_remote_gateways=False,
                                remote_virtual_network={'id': s.id})
                            # use the same peering name for both sides to simplify peering termination
                            network_client.virtual_network_peerings.create_or_update(i.rg, i.name, name, peer_model)
                            # create a route in i private route table to silb private ip

                            rt = network_client.route_tables.get(i.rg, 'private_route_table')
                            rt.routes.append({'address_prefix': '0.0.0.0/0', 'next_hop_type': 'VirtualAppliance',
                                              'next_hop_ip_address': s.tags['tvpc_silb_private_address'],
                                              'name': 'default_route'})
                            network_client.route_tables.create_or_update(i.rg, 'private_route_table', rt)
                            logger.info("Build peering between {} and {}".format(i.id, s.id))
                        except Exception as e:
                            logger.warning("Unable to Build peering between {} and {}".format(i.id, s.id))
                            logger.error("{}".format(e))
                        break

        """
        Any VNET peerings still in the tvpc_silb_vnets do not have properly tagged participating VNETs
        Remove routes to SILB from remote VNET
        Remove peering from SILB VNET
        """
        for s in tvpc_silb_vnets:
            for x in s.virtual_network_peerings:
                try:
                    temp = x.remote_virtual_network.id.split('/')
                    remote_resource_group_name = temp[4]
                    remote_vnet_name = temp[8]
                    network_client.routes.delete(remote_resource_group_name, 'private_route_table', 'default_route')
                    network_client.virtual_network_peerings.delete(s.rg, s.name, x.name)
                    network_client.virtual_network_peerings.delete(remote_resource_group_name, remote_vnet_name, x.name)
                    logger.info("Removed peering between {} and {}".format(s.name, remote_vnet_name))
                except Exception as e:
                    logger.warning("Unable to remove peering between {} and {}".format(s.name, remote_vnet_name))
                    logger.error("{}".format(e))

        """
        If there are participant VNETs with tags but no SILB VPC, go through and remove peering connections and routes.
        For instance, if removed SILB VNET
        """
        for i in tvpc_participants:
            if not i.partner:
                for x in i.virtual_network_peerings:
                    try:
                        temp = x.remote_virtual_network.id.split('/')
                        remote_resource_group_name = temp[4]
                        remote_vnet_name = temp[8]
                        network_client.routes.delete(i.rg, 'private_route_table', 'default_route')
                        network_client.virtual_network_peerings.delete(i.rg, i.name, x.name)
                        network_client.virtual_network_peerings.delete(remote_resource_group_name,
                                                                       remote_vnet_name, x.name)
                        logger.info("Removed peering between {} and {}".format(i.name, remote_vnet_name))
                    except Exception as e:
                        logger.warning("Unable to remove peering between {} and {}".format(i.name, remote_vnet_name))
                        logger.error("{}".format(e))

        # empty garbage and wait
        counter = 0
        while counter < 60:
            gc.collect(generation=2)
            counter += 1
            time.sleep(1)
            print(counter)
