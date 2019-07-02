# Azure Scalable, Secure, Highly Available, Cisco CSR1000v Automated Routing Solution
## Description
Summary: This program creates an Azure Standard Private Load Balancer to Cisco CSR1000vs with automated VNET peering and
 UDR installation .

Application owners and developers desire rapid on-demand provisioning of their applications. They also need their 
applications connected to the enterprise network in compliance with IT polices. This is accomplished through predefined
 KEY/VALUE pairs provided by IT operations to the application owners and developers. Once the KEY/VALUE pairs are tagged 
 to a application VNETs, the poller program automatically configures bi-directional VNET peering between the router SILB
 VNET and peer VNETs. The poller program also installs a UDR default route in the peer VNET with the next-hop of the
 private standard load balancer VIP. When the KEY/VALUE tag is removed from a VNET the peering connections and UDRs
 are removed.

## Installation
1. Clone the repository from GitHub
    - ````````git clone https://wwwin-github.cisco.com/stmosher/azure_silb_cisco_csr1000v.gitt````````
2. Create a virtual environment
    - `````` python3 -m venv venv ``````
3. Activate virtual environment
    - ```````` source venv/bin/activate```````` 
4. Edit set_env_vars_empty.sh with your appropriate Azure credentials. See example below:
    - ````````#!/usr/bin/env bash ````````
    - ````````export dmvpn_password='' ````````
    - ````````export router_username='' ````````
    - ````````export router_password='' ````````
    - ````````export AZURE_TENANT_ID='' ````````
    - ````````export AZURE_CLIENT_ID='' ````````
    - ````````export AZURE_CLIENT_SECRET='' ````````
    - ````````export AZURE_SUBSCRIPTION_ID='' ````````
5. Run script to set environment variables:
    - ````````source ./set_env_vars_empty.sh````````
6. Install application requirements:
    - ````````pip install -r requirements.txt````````
7. In config.py Add Regions
8. In config.py if using Cisco Smart Licensing, set per region key 'smart_licensing' value to 'True', otherwise set to 
'False'
9. In config.py if using Cisco Smart Licensing, add appropriate license_token, license_feature_set, and 
license_throughput dictionaries. The program will select the best license available for the instance_type you deploy
10. In config.py if using Cisco Smart Licensing, configure appropriate, dns_server, email_address, 
and smart_licensing_server

## Usage
To use the Cisco CSR1000v in Azure, you must first accept the terms for the VM software. Use the accept_terms.py script 
to automate this. Edit lines 80 to 82 with the appropriate information. Save and run with python accept_terms.py.

To deploy the demo, fill out the below variables near the end of the script:
- ````````azure_vm_publisher = 'cisco',````````--VM info
- ````````azure_vm_offer = 'cisco-csr-1000v',````````--VM info
- ````````azure_vm_sku = '16_10-byol',````````--VM info
- ````````region = 'westus'````````--Region for deployment
- ````````instance_type = 'Standard_DS3_v2'````````--Azure Instance Type
- ````````cluster = 'dev'````````--Name of router cluster. This will be the value for participating VNETs(Key is tvpc_program_key defined in config.py)
- ````````asn = '65535'````````--asn for deployed routers
- ````````private_vnet_address_space = '10.100.0.0/21'````````--Private Azure subnets are subnetted from this space
- ````````public_vnet_address_space = '172.16.0.0/21'````````--Public Azure subnets are carved from this space
- ````````unique_prefix = 'sm10'````````--Random prefix to ensure names are unique
- ````````router_list = [1, 1, 1, 2]````````--Each element is a number of routers to be deployed per VNET
- ````````types = ['hub', 'vnet', 'vnet', 'silb']````````--Types of VNETS. Hub must be deployed in first position! The other VNETs will need to follow as they will receive the hub router's public and tunnel IP addresses. VNET types are hub, spoke, silb, vnet.

To start the poller, within virtual environment $python3 poller.py

## Fault Tolerance
Routers are deployed in an availability set.
Standard Load Balancer runs health probes to ensure routers are operational.
Routers run internal script to fail SILB probe when loss of BGP adjacency with BGP Peer.

## Enterprise Design
Separate clusters replace the need for customer vrfs on routers. Calculate the instance sizes for individual IPSEC throughput capacity and multiply
by number for load balanced routers for total capacity. You can stop and start routers as capacity demands change.
The DMVPN can be used for inter region VNET traffic across the MS Azure backbone. The DMVPN can also be used to connect to 
enterprise site via the Internet. If an Express Route is used for traffic back to enterprise sites, I suggest using a separate
gigabit ethernet interface in new vrf with a second DMVPN cloud for enterprise site connectivity.

Each SILB VNET can have a maximum of 500 VNET peers as of 06/28/19.

## Demo
https://youtu.be/t-ETh3PtpSI

## Logging
Logs are found in "azure_poller.log".

### Notes
Tested with Python 3.7.2

Cisco IOS-XE 16.x

