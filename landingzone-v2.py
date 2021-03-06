#!/usr/bin/env python3
""" This script requests Landing Zone supernets and updates phpIPAM.

This script requests Landing Zone supernets based on the AWS region and
updates phpIPAM accordingly, including the creation of further subnets and
reserving IP addresses.

Including in the Landing Zones is:
    - Shared Services VPC
    - vEdge VPC

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
    "us-east-1": {
        "network": 74,
        "dns": 2,
        "tgwId": "tgw-0031a74e3b340a704",
        "tgwMainRouteTable": ""
    },
    "eu-west-1": {
        "network": 76,
        "dns": 3,
        "tgwId": "tgw-0097de3283b71ced1",
        "tgwMainRouteTable": ""
    },
    "eu-west-2": {
        "network": 75,
        "dns": 3,
        "tgwId": "tgw-000816d04ea49d358",
        "tgwMainRouteTable": ""
    },
    "eu-central-1": {
        "network": 918,
        "dns": 3,
        "tgwId": "tgw-06173001949ff1ea2",
        "tgwMainRouteTable": "tgw-rtb-05f55e0d134692083"
    },
    "ap-southeast-2": {
        "network": 106,
        "dns": 2,
        "tgwId": "tgw-0fc230fd5535b3ddf",
        "tgwMainRouteTable": ""
    }
}

def loadConfig():
    '''
    Load a configuration file into global variables
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

def createSsVpc(region, cvpn):
    '''
    Create subnets for the Shared Services VPC

    :param str region: region where we deploy the VPC
    :param bool cvpn: whether to add subnets for CVPN firewalls
    :return: JSON object with server response
    :rtype: str
    '''

    global config, regionalSettings
    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    descriptionPrePend = 'Shared Services'
    description = descriptionPrePend + ' VpcCidr'
    r = json.loads(requestSubnet(regionalSettings[region]['network'], 19, description, regionalSettings[region]['dns']))
    if r['code'] == 201:
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)

        description = descriptionPrePend + ' Private subnet AZ A'
        privatea = json.loads(requestSubnet(r['id'], 22, description, regionalSettings[region]['dns']))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Private subnet AZ B'
        privateb = json.loads(requestSubnet(r['id'], 22, description, regionalSettings[region]['dns']))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Transit subnet AZ B'
        transitb = json.loads(requestSubnet(r['id'], 28, description, 0, 0, 'last'))
        tmp = {'id': transitb['id'], 'subnet': transitb['data'], 'description': description}
        output['data'].append(tmp)
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
        transitb_res2 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))
        transitb_res3 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Transit subnet AZ A'
        transita = json.loads(requestSubnet(r['id'], 28, description, 0, 0, 'last'))
        tmp = {'id': transita['id'], 'subnet': transita['data'], 'description': description}
        output['data'].append(tmp)
        transita_gw = json.loads(createFirstAddress(transita['id'], 'Default gateway', 1))
        transita_res2 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))
        transita_res3 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Public subnet AZ B'
        publicb = json.loads(requestSubnet(r['id'], 23, description, regionalSettings[region]['dns'], 1, 'last'))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Public subnet AZ A'
        publica = json.loads(requestSubnet(r['id'], 23, description, regionalSettings[region]['dns'], 1 , 'last'))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_res2 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))

        if cvpn:
            description = descriptionPrePend + ' CVPN subnet'
            cvpna = json.loads(requestSubnet(r['id'], 22, description, regionalSettings[region]['dns'], 0, 'last'))
            tmp = {'id': cvpna['id'], 'subnet': cvpna['data'], 'description': description}
            output['data'].append(tmp)
            cvpna_gw = json.loads(createFirstAddress(cvpna['id'], 'Default gateway', 1))

        output['code'] = 200
        output['success'] = 'true'
    else:
        output['code'] = 500
        output['success'] = 'false'
    return output

def createvEdgeVpc(region):
    '''
    Create subnets for the vEdge VPC

    :param str region: region where we deploy the VPC
    :return: JSON object with server response
    :rtype: str
    '''

    global config, regionalSettings
    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    descriptionPrePend = 'vEdge'
    description = descriptionPrePend + ' VpcCidr'
    r = json.loads(requestSubnet(regionalSettings[region]['network'], 25, description, regionalSettings[region]['dns'], 1, 'last'))
    if r['code'] == 201:
        description = descriptionPrePend + ' Public subnet AZ A'
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)
    
        description = descriptionPrePend + ' Private subnet AZ A'
        privatea = json.loads(requestSubnet(r['id'], 28, description, regionalSettings[region]['dns']))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Private subnet AZ B'
        privateb = json.loads(requestSubnet(r['id'], 28, description, regionalSettings[region]['dns']))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Public subnet AZ A'
        publica = json.loads(requestSubnet(r['id'], 28, description, regionalSettings[region]['dns']))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_res2 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Public subnet AZ B'
        publicb = json.loads(requestSubnet(r['id'], 28, description, regionalSettings[region]['dns']))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Transit subnet AZ B'
        transitb = json.loads(requestSubnet(r['id'], 28, description, 0, 0, 'last'))
        tmp = {'id': transitb['id'], 'subnet': transitb['data'], 'description': description}
        output['data'].append(tmp)
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
        transitb_res2 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))
        transitb_res3 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Transit subnet AZ A'
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
   
def createCfYaml(region, ipam, template, cvpn = False):
    '''
    Create a CloudFormation YAML file to create the VPC

    :param str region: AWS region
    :param dict ipam_ss: Dictionary with Shared Services subnets and related information
    :param dict ipam_ve: Dictionary with vEdge subnets and related information
    :param str template: YAML Template
    :return: YAML
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

    url = f"https://{config['server']}/api/{config['appid']}/subnets/{regionalSettings[region]['network']}/"
    r = json.loads(requests.request("GET", url, headers=headers, data=payload).text)
    regionalCidr = r['data']['subnet'] + '/' + r['data']['mask']

    tpl = Template(template)
    tplArgs = {
        'nameservers': nameservers,
        'region': region,
        'regionalCidr': regionalCidr,
        'ssVpcCidr': ipam[0][0]['subnet'],
        'ssPrivateSubnet1': ipam[0][1]['subnet'],
        'ssPrivateSubnet1Description': ipam[0][1]['description'],
        'ssPrivateSubnet2': ipam[0][2]['subnet'],
        'ssPrivateSubnet2Description': ipam[0][2]['description'],
        'ssTransitSubnet2': ipam[0][3]['subnet'],
        'ssTransitSubnet2Description': ipam[0][3]['description'],
        'ssTransitSubnet1': ipam[0][4]['subnet'],
        'ssTransitSubnet1Description': ipam[0][4]['description'],
        'ssPublicSubnet2': ipam[0][5]['subnet'],
        'ssPublicSubnet2Description': ipam[0][5]['description'],
        'ssPublicSubnet1': ipam[0][6]['subnet'],
        'ssPublicSubnet1Description': ipam[0][6]['description'],
        'veVpcCidr': ipam[1][0]['subnet'],
        'vePrivateSubnet1': ipam[1][1]['subnet'],
        'vePrivateSubnet1Description': ipam[1][1]['description'],
        'vePrivateSubnet2': ipam[1][2]['subnet'],
        'vePrivateSubnet2Description': ipam[1][2]['description'],
        'vePublicSubnet1': ipam[1][3]['subnet'],
        'vePublicSubnet1Description': ipam[1][3]['description'],
        'vePublicSubnet2': ipam[1][4]['subnet'],
        'vePublicSubnet2Description': ipam[1][4]['description'],
        'veTransitSubnet2': ipam[1][5]['subnet'],
        'veTransitSubnet2Description': ipam[1][5]['description'],
        'veTransitSubnet1': ipam[1][6]['subnet'],
        'veTransitSubnet1Description': ipam[1][6]['description'],
        'TgId': regionalSettings[region]['tgwId'],
        'TgMainRouteTable': regionalSettings[region]['tgwMainRouteTable'],
    }

    return tpl.render (tplArgs)

def main():
    '''
    Main script logic
    '''

    loadConfig()

    global config, regionalSettings

    # Read input arguments
    argp = argparse.ArgumentParser(description = 'Create Landing Zone networks.')
    argp.add_argument('region', type=str, help='AWS region where the networks reside.')
    argp.add_argument('template', type=str, help='Template file name')
    argp.add_argument('--cvpn', type=str, default='no', help='Whether to provision networks for CVPN in.')
    args = argp.parse_args()
    region = args.region
    template = args.template
    if args.cvpn == 'yes':
        cvpn = True
    else:
        cvpn = False

    output = {'code': 0, 'success': 'false'}
    output['data'] = []
    output['yaml'] = {}

    if region in regionalSettings:
        ssvpc = createSsVpc(region, cvpn)
        if ssvpc['code'] == 200:
            output['code'] = 200
            output['success'] = 'true'
            output['data'].append(ssvpc['data'])
            output['data'].append(createvEdgeVpc(region)['data'])
            with open(template) as infile:
                output['yaml'] = createCfYaml(region, output['data'], infile.read(), cvpn)
        else:
            output['code'] = 500
            output['success'] = 'false'
            output['data'] = {'description': 'General failure trying to create networks.'}
    else:
        output['data'] = {'description': 'Region not defined or recognised.'}

    output['time'] = time.time() - starttime
    return output

if __name__ == "__main__":
    print(json.dumps(main()))
