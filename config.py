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


class Settings:
    # regions added to the below will be considered for IPSEC overlay participation
    regions = {
        'eastus': {
            'eligible_default': 'True',
            'smart_licensing': 'True',
            'username': os.environ.get('router_username'),
            'password': os.environ.get('router_password'),
        },
        'westus': {
            'eligible_default': 'True',
            'smart_licensing': 'True',
            'username': os.environ.get('router_username'),
            'password': os.environ.get('router_password'),
        }
    }
    instance_types = {
        'Standard_D2_v2': 900,
        'Standard_DS2_v2': 900,
        'Standard_D3_v2': 200,
        'Standard_DS3_v2': 2000,
        'Standard_D4_v2': 4400,
        'Standard_DS4_v2': 4400
    }
    # Smart Licensing Information
    licenses = [
        {'license_token': '123456',
         'license_feature_set': 'ax',
         'license_throughput': 5000
         }
    ]
    dns_server = '8.8.8.8'
    email_address = 'stmosher@cisco.com'
    smart_licensing_server = 'https://tools.cisco.com/its/service/oddce/services/DDCEService'

    # Items with below key in AWS TAG will be considered participating in program
    tvpc_program_key = 'auto_tvpc_cluster_member'
    # Router DMVPN Tunnel addresses are from the address space below
    dmvpn_address_space = '192.168.254.0/23'
    dmvpn_password = os.environ.get('dmvpn_password')
