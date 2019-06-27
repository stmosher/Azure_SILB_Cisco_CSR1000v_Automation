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

import requests
import json
import os


class AzureTermsHelper:
    def __init__(self, tenant_id, api_client_id, api_client_secret, subscription_id, publisher, offer, sku):
        self.tenant_id = tenant_id
        self.api_client_id = api_client_id
        self.api_client_secret = api_client_secret
        self.subscription_id = subscription_id
        self.publisher = publisher
        self.offer = offer
        self.sku = sku

    def get_bearer_token(self):
        url = 'https://login.microsoftonline.com/{}/oauth2/token'.format(self.tenant_id)
        data = {'grant_type': 'client_credentials', 'client_id': self.api_client_id, 'client_secret': self.api_client_secret,
                'resource': 'https://management.azure.com/'}
        r = requests.post(url, data=data)
        body = r.json()
        self.bearer_token = body['access_token']
        print(f'This is your bearer token: {self.bearer_token}')

    def get_terms(self):
        headers = {'Authorization': 'Bearer {}'.format(self.bearer_token), 'Content-Type': 'application/json'}
        url = f'https://management.azure.com/subscriptions/{self.subscription_id}/providers/Microsoft.MarketplaceOrdering/offertypes/virtualmachine/publishers/{self.publisher}/offers/{self.offer}/plans/{self.sku}/agreements/current?api-version=2015-06-01'
        r = requests.get(url, headers=headers)
        self.body = r.json()
        terms_link = self.body['properties']['licenseTextLink']
        print(f'License terms available for review below: \n{terms_link}')

    def accept_terms(self):
        self.body['properties']['accepted'] = True
        headers = {'Authorization': 'Bearer {}'.format(self.bearer_token), 'Content-Type': 'application/json'}
        url = f'https://management.azure.com/subscriptions/{self.subscription_id}/providers/Microsoft.MarketplaceOrdering/offertypes/virtualmachine/publishers/{self.publisher}/offers/{self.offer}/plans/{self.sku}/agreements/current?api-version=2015-06-01'
        r = requests.put(url, headers=headers, data=json.dumps(self.body))
        body = r.json()
        print(f'Below are the results: \n{body}')

    def accept(self):
        self.get_bearer_token()
        self.get_terms()
        if self.body['properties']['accepted'] == True:
            print(f'Terms have already been accepted for subscription {subscription_id}')
        else:
            self.accept_terms()


if __name__ == '__main__':
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    api_client_id = os.environ.get('AZURE_CLIENT_ID'),
    api_client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')

    publisher = 'cisco'
    offer = 'cisco-csr-1000v'
    sku = 'csr-azure-byol'

    worker = AzureTermsHelper(tenant_id, api_client_id, api_client_secret, subscription_id, publisher, offer, sku)
    worker.get_bearer_token()
    worker.get_terms()
    worker.accept_terms()
    worker.accept()
