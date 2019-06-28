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
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from multiprocessing import Process


def remove_vnet(rgn):
    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
    credentials = ServicePrincipalCredentials(
        client_id=os.environ.get('AZURE_CLIENT_ID'),
        secret=os.environ.get('AZURE_CLIENT_SECRET'),
        tenant=os.environ.get('AZURE_TENANT_ID')
    )
    try:
        resource_client = ResourceManagementClient(credentials, subscription_id)
        result = resource_client.resource_groups.delete(
            resource_group_name=rgn
        )
        result.wait()
    except:
        pass


if __name__ == '__main__':
    resource_group_name = ['sm100', 'sm101', 'sm102', 'sm103', 'swm0']
    processes = list()

    for i in resource_group_name:
        p = Process(target=remove_vnet, args=(i,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    print('Done')
