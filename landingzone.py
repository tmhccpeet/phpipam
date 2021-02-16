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
        "ap-southeast-2": 2
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

    global config, regionalNetworks, regionalInternalDNS
    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    descriptionPrePend = 'Shared Services'
    description = descriptionPrePend + ' VpcCidr'
    r = json.loads(requestSubnet(regionalNetworks[region], 20, description, regionalInternalDNS[region]))
    if r['code'] == 201:
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)

        description = descriptionPrePend + ' Private subnet AZ A'
        privatea = json.loads(requestSubnet(r['id'], 23, description, regionalInternalDNS[region]))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Private subnet AZ B'
        privateb = json.loads(requestSubnet(r['id'], 23, description, regionalInternalDNS[region]))
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
        publicb = json.loads(requestSubnet(r['id'], 23, description, regionalInternalDNS[region], 1, 'last'))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))

        description = descriptionPrePend + ' Public subnet AZ A'
        publica = json.loads(requestSubnet(r['id'], 23, description, regionalInternalDNS[region], 1 , 'last'))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_res2 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))

        if cvpn:
            description = descriptionPrePend + ' Public CVPN subnet AZ B'
            cvpnb = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region], 0, 'last'))
            tmp = {'id': cvpnb['id'], 'subnet': cvpnb['data'], 'description': description}
            output['data'].append(tmp)
            cvpnb_gw = json.loads(createFirstAddress(cvpnb['id'], 'Default gateway', 1))
            cvpnb_res2 = json.loads(createFirstAddress(cvpnb['id'], 'Reserved by AWS'))
            cvpnb_res3 = json.loads(createFirstAddress(cvpnb['id'], 'Reserved by AWS'))
    
            description = descriptionPrePend + ' Public CVPN subnet AZ A'
            cvpna = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region], 0 , 'last'))
            tmp = {'id': cvpna['id'], 'subnet': cvpna['data'], 'description': description}
            output['data'].append(tmp)
            cvpna_gw = json.loads(createFirstAddress(cvpna['id'], 'Default gateway', 1))
            cvpna_res2 = json.loads(createFirstAddress(cvpna['id'], 'Reserved by AWS'))
            cvpna_res3 = json.loads(createFirstAddress(cvpna['id'], 'Reserved by AWS'))

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

    global config, regionalNetworks, regionalInternalDNS
    output = {'code': 0, 'success': 'false'}
    output['data'] = []

    descriptionPrePend = 'vEdge'
    description = descriptionPrePend + ' VpcCidr'
    r = json.loads(requestSubnet(regionalNetworks[region], 25, description, regionalInternalDNS[region], 1, 'last'))
    if r['code'] == 201:
        description = descriptionPrePend + ' Public subnet AZ A'
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)
    
        description = descriptionPrePend + ' Private subnet AZ A'
        privatea = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Private subnet AZ B'
        privateb = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Public subnet AZ A'
        publica = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_res2 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Public subnet AZ B'
        publicb = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Temp subnet AZ A'
        tempa = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': tempa['id'], 'subnet': tempa['data'], 'description': description}
        output['data'].append(tmp)
        tempa_gw = json.loads(createFirstAddress(tempa['id'], 'Default gateway', 1))
        tempa_res2 = json.loads(createFirstAddress(tempa['id'], 'Reserved by AWS'))
        tempa_res3 = json.loads(createFirstAddress(tempa['id'], 'Reserved by AWS'))
    
        description = descriptionPrePend + ' Temp subnet AZ B'
        tempb = json.loads(requestSubnet(r['id'], 28, description, regionalInternalDNS[region]))
        tmp = {'id': tempb['id'], 'subnet': tempb['data'], 'description': description}
        output['data'].append(tmp)
        tempb_gw = json.loads(createFirstAddress(tempb['id'], 'Default gateway', 1))
        tempb_res2 = json.loads(createFirstAddress(tempb['id'], 'Reserved by AWS'))
        tempb_res3 = json.loads(createFirstAddress(tempb['id'], 'Reserved by AWS'))
    
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

    global config, regionalInternalDNS

    url = f"https://{config['server']}/api/{config['appid']}/tools/nameservers/{regionalInternalDNS[region]}/"
    headers = {
            'token': config['token'],
            'Content-Type': 'application/json'
    }
    payload = ''

    r = json.loads(requests.request("GET", url, headers=headers, data=payload).text)
    nameservers = r['data']['namesrv1'].split(';')
    tpl = Template(template)
    tplArgs = {
        'nameservers': nameservers,
        'region': region,
        'ssVpcCidr': ipam[0][0]['subnet'],
        'ssPrivateAIp': ipam[0][1]['subnet'],
        'ssPrivateADescription': ipam[0][1]['description'],
        'ssPrivateBIp': ipam[0][2]['subnet'],
        'ssPrivateBDescription': ipam[0][2]['description'],
        'ssTransitBIp': ipam[0][3]['subnet'],
        'ssTransitBDescription': ipam[0][3]['description'],
        'ssTransitAIp': ipam[0][4]['subnet'],
        'ssTransitADescription': ipam[0][4]['description'],
        'ssPublicBIp': ipam[0][5]['subnet'],
        'ssPublicBDescription': ipam[0][5]['description'],
        'ssPublicAIp': ipam[0][6]['subnet'],
        'ssPublicADescription': ipam[0][6]['description'],
        'ssNatGatewayAEIPName': 'Shared Services NAT Gateway AZ A External IP',
        'ssNatGatewayAName': 'Shared Services NAT Gateway AZ A',
        'ssNatGatewayBEIPName': 'Shared Services NAT Gateway AZ B External IP',
        'ssNatGatewayBName': 'Shared Services NAT Gateway AZ B',
        'cvpn': cvpn,
        'veVpcCidr': ipam[1][0]['subnet'],
        'vePrivateAIp': ipam[1][1]['subnet'],
        'vePrivateADescription': ipam[1][1]['description'],
        'vePrivateBIp': ipam[1][2]['subnet'],
        'vePrivateBDescription': ipam[1][2]['description'],
        'vePublicAIp': ipam[1][3]['subnet'],
        'vePublicADescription': ipam[1][3]['description'],
        'vePublicBIp': ipam[1][4]['subnet'],
        'vePublicBDescription': ipam[1][4]['description'],
        'veTransitBIp': ipam[1][7]['subnet'],
        'veTransitBDescription': ipam[1][7]['description'],
        'veTransitAIp': ipam[1][8]['subnet'],
        'veTransitADescription': ipam[1][8]['description']
    }
    if cvpn:
        tplArgs['ssCvpnBIp'] = ipam[0][7]['subnet']
        tplArgs['ssCvpnBDescription'] = ipam[0][7]['description']
        tplArgs['ssCvpnAIp'] = ipam[0][8]['subnet']
        tplArgs['ssCvpnADescription'] = ipam[0][8]['description']

    return tpl.render (tplArgs)

def main():
    '''
    Main script logic
    '''

    loadConfig()

    global config

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

    if region in regionalNetworks:
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
