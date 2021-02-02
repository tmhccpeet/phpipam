#!/usr/bin/env python3
""" This script requests a spoke supernet and updates phpIPAM.

This script requests a spoke supernet based on the AWS region and
updates phpIPAM accordingly, including the creation of further subnets and
reserving IP addresses.

--

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Peet van de Sande"
__contact__ = "pvandesande@tmhcc.com"
__license__ = "GPLv3"

import argparse
import csv
import requests
import json
import urllib.parse
import ipaddress

config = {}
regionalNetworks = {
        "us-east-1": 74,
        "eu-west-2": 75,
        "eu-west-1": 76,
        "ap-southeast-2": 106
}
regionalInternalDNS = {
        "us-east-1": 2,
        "eu-west-2": 3,
        "eu-west-1": 3,
        "ap-southeast-2": 0
}
SPOKESIZE = 22 # Supernet size for a standard spoke

def load_config():
    '''
    Load a configuration file
    '''

    global config

    with open('config.json') as config_file:
        config = json.load(config_file)

def requestSubnet(masterId, size, description, nameserverId = 0, allowRequests = 1, position = 'first'):
    '''
    Request a subnet from a supernet and update its details

    :param int masterId: Subnet ID of the supernet
    :param int size: Size of the requested subnet in bits (1 - 31)
    :param str description: Human-readable description of what this subnet is used for
    :param int nameserverId: ID of nameserver set in phpIPAM
    :param int allowRequests: Define whether IP addresses may be requested from this subnet
    :param str position: Where in the supernet sits the requested subnet
    :return: JSON object with server response
    :rtype: str
    '''
    global config
    url = f"https://{config['server']}/api/{config['appid']}/subnets/{masterId}/{position}_subnet/{size}/"
    headers = {
            'token': config['token'],
            'Content-Type': 'application/json'
    }
    payload = f"""{{
        \"description\": \"{description}\",
        \"pingSubnet\": \"0\",
        \"allowRequests\": \"{allowRequests}\",
        \"nameserverId\": \"{nameserverId}\"
    }}"""

    return requests.request("POST", url, headers=headers, data=payload).text

def createFirstAddress(subnetId, description, isGateway = 0):
    '''
    Create an IP address in a specific subnet

    :param int subnetId: ID of the subnet
    :param str description: Human-readable description of what this subnet is used for
    :param int isGateway: Define whether the device is a gateway (router)
    :return: JSON object with server response
    :rtype: str
    '''
    global config
    url = f"https://{config['server']}/api/{config['appid']}/addresses/first_free/"
    headers = {
            'token': config['token'],
            'Content-Type': 'application/json'
    }
    payload = f"""{{
        \"subnetId\": \"{subnetId}\",
        \"description\": \"{description}\",
        \"is_gateway\": \"{isGateway}\"
    }}"""

    return requests.request("POST", url, headers=headers, data=payload).text


def main():
    '''
    Main script logic
    '''
    load_config()

    global config, regionalNetworks, regionalInternalDNS

    # Read input arguments
    argp = argparse.ArgumentParser(description = 'Create spoke network.')
    argp.add_argument('--region', type=str, nargs=1, help='AWS region where the spoke resides')
    argp.add_argument('--description', type=str, nargs=1, help='Short description of the spoke')
    args = argp.parse_args()
    region = args.region[0]
    description = args.description[0]

    r = json.loads(requestSubnet(regionalNetworks[region], SPOKESIZE, description, regionalInternalDNS[region]))
    if r['code'] == 201:
        print(f"Created subnet({r['id']}): {r['data']}")

        proda = json.loads(requestSubnet(r['id'], 24, description + ' Production AZ A', regionalInternalDNS[region]))
        print(f"Created subnet({proda['id']}): {proda['data']}")
        proda_gw = json.loads(createFirstAddress(proda['id'], 'Default gateway', 1))
        print(f"Marked {proda_gw['data']} as default gateway")
        proda_dns = json.loads(createFirstAddress(proda['id'], 'AWS DNS'))
        print(f"Marked {proda_dns['data']} as AWS DNS")
        proda_res3 = json.loads(createFirstAddress(proda['id'], 'Reserved by AWS'))
        print(f"Marked {proda_res3['data']} as Reserved by AWS")

        prodb = json.loads(requestSubnet(r['id'], 24, description + ' Production AZ B', regionalInternalDNS[region]))
        print(f"Created subnet({prodb['id']}): {prodb['data']}")
        prodb_gw = json.loads(createFirstAddress(prodb['id'], 'Default gateway', 1))
        print(f"Marked {prodb_gw['data']} as default gateway")
        prodb_res2 = json.loads(createFirstAddress(prodb['id'], 'Reserved by AWS'))
        print(f"Marked {prodb_res2['data']} as Reserved by AWS")
        prodb_res3 = json.loads(createFirstAddress(prodb['id'], 'Reserved by AWS'))
        print(f"Marked {prodb_res3['data']} as Reserved by AWS")

        transitb = json.loads(requestSubnet(r['id'], 28, description + ' Transit AZ B', 0, 0, 'last'))
        print(f"Created subnet({transitb['id']}): {transitb['data']}")
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
        print(f"Marked {transitb_gw['data']} as default gateway")

        transita = json.loads(requestSubnet(r['id'], 28, description + ' Transit AZ A', 0, 0, 'last'))
        print(f"Created subnet({transita['id']}): {transita['data']}")
        transita_gw = json.loads(createFirstAddress(transita['id'], 'Default gateway', 1))
        print(f"Marked {transita_gw['data']} as default gateway")

if __name__ == "__main__":
    main()
