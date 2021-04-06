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

import sys
import argparse
import requests
import json
import time
from jinja2 import Template

starttime = time.time()
config = {}
regionalSettings = {
    "ap-southeast-2": {
        "network": 106,
        "dns": 2,
        "tgwId": "tgw-0fc230fd5535b3ddf",
        "tgwInspectionAttachment": "",
        "tgwMainRouteTable": "",
        "tgwInspectionRouteTable": "",
        "dhcpOptions": ""
    },
    "us-east-1": {
        "network": 74,
        "dns": 2,
        "tgwId": "tgw-0031a74e3b340a704",
        "tgwInspectionAttachment": "",
        "tgwMainRouteTable": "",
        "tgwInspectionRouteTable": "",
        "dhcpOptions": ""
    },
    "eu-west-1": {
        "network": 76,
        "dns": 3,
        "tgwId": "tgw-0031a74e3b340a704",
        "tgwInspectionAttachment": "",
        "tgwMainRouteTable": "",
        "tgwInspectionRouteTable": "",
        "dhcpOptions": ""
    },
    "eu-west-2": {
        "network": 75,
        "dns": 3,
        "tgwId": "tgw-000816d04ea49d358",
        "tgwInspectionAttachment": "",
        "tgwMainRouteTable": "",
        "tgwInspectionRouteTable": "",
        "dhcpOptions": ""
    },
    "eu-central-1": {
        "network": 918,
        "dns": 3,
        "tgwId": "tgw-06173001949ff1ea2",
        "tgwInspectionAttachment": "tgw-attach-068d1df133ade8cac",
        "tgwMainRouteTable": "tgw-rtb-05f55e0d134692083",
        "tgwInspectionRouteTable": "tgw-rtb-05f55e0d134692083",
        "dhcpOptions": "dopt-0a11e07c9afdbb7d8"
    }
}

SPOKESIZE = 22 # Supernet size for a standard spoke

def loadConfig():
    '''
    Load a configuration file
    '''

    global config

    try:
        with open('config.json') as config_file:
            config = json.load(config_file)
    except IOError:
        try:
            with open('/etc/netops/phpipam/config.json') as config_file:
                config = json.load(config_file)
        except IOError:
            sys.exit(json.dumps({'code': 501, 'success': 'false', 'data': {'description': "Can't find config file."}}))

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

def createSpoke(region, account, size = 22):
    '''
    Calculate and create subnets plus reserved IP addresses

    :param str region: AWS region
    :param str account: Name of the account
    :param int size: CIDR size of the VPC
    :return: JSON object with server response
    :rtype: str
    '''
    global config, regionalSettings 
    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    description = account + ' VpcCidr'
    r = json.loads(requestSubnet(regionalSettings[region]['network'], size, description, regionalSettings[region]['dns']))
    if r['code'] == 201:
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)

        description = account + ' Private subnet AZ A'
        privatea = json.loads(requestSubnet(r['id'], 24, description, regionalSettings[region]['dns']))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))

        description = account + ' Private subnet AZ B'
        privateb = json.loads(requestSubnet(r['id'], 24, description, regionalSettings[region]['dns']))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))

        description = account + ' Transit subnet AZ B'
        transitb = json.loads(requestSubnet(r['id'], 28, description, 0, 0, 'last'))
        tmp = {'id': transitb['id'], 'subnet': transitb['data'], 'description': description}
        output['data'].append(tmp)
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
        transitb_res2 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))
        transitb_res3 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))

        description = account + ' Transit subnet AZ A'
        transita = json.loads(requestSubnet(r['id'], 28, description, 0, 0, 'last'))
        tmp = {'id': transita['id'], 'subnet': transita['data'], 'description': description}
        output['data'].append(tmp)
        transita_gw = json.loads(createFirstAddress(transita['id'], 'Default gateway', 1))
        transita_res2 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))
        transita_res3 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))
        output['code'] = 200
        output['success'] = 'true'
    else:
        output['code'] = 500
        output['success'] = 'false'
    return output

def renderTemplate(region, account, ipam, template):
    '''
    Render a template to produce the buildspec

    :param str region: AWS region
    :param str account: Account name
    :param str ipam: Dictionary with subnets and related information
    :param str template: Template file
    :return: string
    :rtype: str
    '''

    global config, regionalSettings 
    headers = {
            'token': config['token'],
            'Content-Type': 'application/json'
    }
    payload = ''

    url = f"https://{config['server']}/api/{config['appid']}/tools/nameservers/{regionalSettings[region]['dns']}/"
    r = json.loads(requests.request("GET", url, headers=headers, data=payload).text)
    nameservers = r['data']['namesrv1'].split(';')

    tpl = Template(template)
    return tpl.render (
        nameservers = nameservers,
        account = account,
        region = region,
        vpcCidr = ipam['data'][0]['subnet'],
        privateAIp = ipam['data'][1]['subnet'],
        privateADescription = ipam['data'][1]['description'],
        privateBIp = ipam['data'][2]['subnet'],
        privateBDescription = ipam['data'][2]['description'],
        transitBIp = ipam['data'][3]['subnet'],
        transitBDescription = ipam['data'][3]['description'],
        transitAIp = ipam['data'][4]['subnet'],
        transitADescription = ipam['data'][4]['description'],
        transitGatewayId = regionalSettings[region]['tgwId'],
        transitGatewayInspectionAttachment = regionalSettings[region]['tgwInspectionAttachment'],
        transitGatewayMainRouteTable = regionalSettings[region]['tgwMainRouteTable'],
        transitGatewayInspectionRouteTable = regionalSettings[region]['tgwInspectionRouteTable'],
        dhcpOptionsId = regionalSettings[region]['dhcpOptions']
    )

def main():
    '''
    Main script logic
    '''

    loadConfig()

    global config, regionalSettings

    # Read input arguments
    argp = argparse.ArgumentParser(description = 'Create spoke network, request IP addresses from phpIPAM. Produce buildspec based on input template.')
    argp.add_argument('region', type=str, help='AWS region where the spoke resides')
    argp.add_argument('account', type=str, help='Account name')
    argp.add_argument('template', type=str, help='Template file name')
    args = argp.parse_args()
    region = args.region
    account = args.account
    template = args.template

    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    if region in regionalSettings:
        ipam = createSpoke(region, account, SPOKESIZE)
        if ipam['code'] == 200:
            output['code'] = 200
            output['success'] = 'true'
            output['data'] = ipam['data']
            with open(template) as infile:
                output['buildspec'] = renderTemplate(region, account, ipam, infile.read())
        else:
            output['code'] = 500
            output['success'] = 'false'
    else:
        output['data'] = {'description': 'Region not defined or recognised.'}

    output['time'] = time.time() - starttime
    return output

if __name__ == "__main__":
    print(json.dumps(main()))
