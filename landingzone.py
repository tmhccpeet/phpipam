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

    description = 'Shared Services'
    r = json.loads(requestSubnet(regionalNetworks[region], 20, description + ' VpcCidr', regionalInternalDNS[region]))
    if r['code'] == 201:
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)

        privatea = json.loads(requestSubnet(r['id'], 23, description + ' Private subnet AZ A', regionalInternalDNS[region]))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))

        privateb = json.loads(requestSubnet(r['id'], 23, description + ' Private subnet AZ B', regionalInternalDNS[region]))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))

        transitb = json.loads(requestSubnet(r['id'], 28, description + ' Transit subnet AZ B', 0, 0, 'last'))
        tmp = {'id': transitb['id'], 'subnet': transitb['data'], 'description': description}
        output['data'].append(tmp)
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
        transitb_res2 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))
        transitb_res3 = json.loads(createFirstAddress(transitb['id'], 'Reserved by AWS'))

        transita = json.loads(requestSubnet(r['id'], 28, description + ' Transit subnet AZ A', 0, 0, 'last'))
        tmp = {'id': transita['id'], 'subnet': transita['data'], 'description': description}
        output['data'].append(tmp)
        transita_gw = json.loads(createFirstAddress(transita['id'], 'Default gateway', 1))
        transita_res2 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))
        transita_res3 = json.loads(createFirstAddress(transita['id'], 'Reserved by AWS'))

        if cvpn:
            cvpnb = json.loads(requestSubnet(r['id'], 28, description + ' Public CVPN subnet AZ B', regionalInternalDNS[region], 0, 'last'))
            tmp = {'id': cvpnb['id'], 'subnet': cvpnb['data'], 'description': description}
            output['data'].append(tmp)
            cvpnb_gw = json.loads(createFirstAddress(cvpnb['id'], 'Default gateway', 1))
            cvpnb_res2 = json.loads(createFirstAddress(cvpnb['id'], 'Reserved by AWS'))
            cvpnb_res3 = json.loads(createFirstAddress(cvpnb['id'], 'Reserved by AWS'))
    
            cvpna = json.loads(requestSubnet(r['id'], 28, description + ' Public CVPN subnet AZ A', regionalInternalDNS[region], 0 , 'last'))
            tmp = {'id': cvpna['id'], 'subnet': cvpna['data'], 'description': description}
            output['data'].append(tmp)
            cvpna_gw = json.loads(createFirstAddress(cvpna['id'], 'Default gateway', 1))
            cvpna_res2 = json.loads(createFirstAddress(cvpna['id'], 'Reserved by AWS'))
            cvpna_res3 = json.loads(createFirstAddress(cvpna['id'], 'Reserved by AWS'))

        publicb = json.loads(requestSubnet(r['id'], 23, description + ' Public subnet AZ B', regionalInternalDNS[region], 1, 'last'))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))

        publica = json.loads(requestSubnet(r['id'], 23, description + ' Public subnet AZ A', regionalInternalDNS[region], 1 , 'last'))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_res2 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))

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

    description = 'vEdge'
    r = json.loads(requestSubnet(regionalNetworks[region], 25, description + ' VpcCidr', regionalInternalDNS[region], 1, 'last'))
    if r['code'] == 201:
        tmp = {'id': r['id'], 'subnet': r['data'], 'description': description}
        output['data'].append(tmp)
    
        privatea = json.loads(requestSubnet(r['id'], 28, description + ' Private subnet AZ A', regionalInternalDNS[region]))
        tmp = {'id': privatea['id'], 'subnet': privatea['data'], 'description': description}
        output['data'].append(tmp)
        privatea_gw = json.loads(createFirstAddress(privatea['id'], 'Default gateway', 1))
        privatea_dns = json.loads(createFirstAddress(privatea['id'], 'AWS DNS'))
        privatea_res3 = json.loads(createFirstAddress(privatea['id'], 'Reserved by AWS'))
    
        privateb = json.loads(requestSubnet(r['id'], 28, description + ' Private subnet AZ B', regionalInternalDNS[region]))
        tmp = {'id': privateb['id'], 'subnet': privateb['data'], 'description': description}
        output['data'].append(tmp)
        privateb_gw = json.loads(createFirstAddress(privateb['id'], 'Default gateway', 1))
        privateb_res2 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
        privateb_res3 = json.loads(createFirstAddress(privateb['id'], 'Reserved by AWS'))
    
        publica = json.loads(requestSubnet(r['id'], 28, description + ' Public subnet AZ A', regionalInternalDNS[region]))
        tmp = {'id': publica['id'], 'subnet': publica['data'], 'description': description}
        output['data'].append(tmp)
        publica_gw = json.loads(createFirstAddress(publica['id'], 'Default gateway', 1))
        publica_dns = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
        publica_res3 = json.loads(createFirstAddress(publica['id'], 'Reserved by AWS'))
    
        publicb = json.loads(requestSubnet(r['id'], 28, description + ' Public subnet AZ B', regionalInternalDNS[region]))
        tmp = {'id': publicb['id'], 'subnet': publicb['data'], 'description': description}
        output['data'].append(tmp)
        publicb_gw = json.loads(createFirstAddress(publicb['id'], 'Default gateway', 1))
        publicb_res2 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
        publicb_res3 = json.loads(createFirstAddress(publicb['id'], 'Reserved by AWS'))
    
        tempa = json.loads(requestSubnet(r['id'], 28, description + ' Temp subnet AZ A', regionalInternalDNS[region]))
        tmp = {'id': tempa['id'], 'subnet': tempa['data'], 'description': description}
        output['data'].append(tmp)
        tempa_gw = json.loads(createFirstAddress(tempa['id'], 'Default gateway', 1))
        tempa_dns = json.loads(createFirstAddress(tempa['id'], 'Reserved by AWS'))
        tempa_res3 = json.loads(createFirstAddress(tempa['id'], 'Reserved by AWS'))
    
        tempb = json.loads(requestSubnet(r['id'], 28, description + ' Temp subnet AZ B', regionalInternalDNS[region]))
        tmp = {'id': tempb['id'], 'subnet': tempb['data'], 'description': description}
        output['data'].append(tmp)
        tempb_gw = json.loads(createFirstAddress(tempb['id'], 'Default gateway', 1))
        tempb_res2 = json.loads(createFirstAddress(tempb['id'], 'Reserved by AWS'))
        tempb_res3 = json.loads(createFirstAddress(tempb['id'], 'Reserved by AWS'))
    
        transitb = json.loads(requestSubnet(r['id'], 28, description + ' Transit subnet AZ B', 0, 0, 'last'))
        tmp = {'id': transitb['id'], 'subnet': transitb['data'], 'description': description}
        output['data'].append(tmp)
        transitb_gw = json.loads(createFirstAddress(transitb['id'], 'Default gateway', 1))
    
        transita = json.loads(requestSubnet(r['id'], 28, description + ' Transit subnet AZ A', 0, 0, 'last'))
        tmp = {'id': transita['id'], 'subnet': transita['data'], 'description': description}
        output['data'].append(tmp)
        transita_gw = json.loads(createFirstAddress(transita['id'], 'Default gateway', 1))

        output['code'] = 200
        output['success'] = 'true'
    else:
        output['code'] = 500
        output['success'] = 'false'
    return output
   
def main():
    '''
    Main script logic
    '''

    loadConfig()

    global config

    # Read input arguments
    argp = argparse.ArgumentParser(description = 'Create Landing Zone networks.')
    argp.add_argument('region', type=str, help='AWS region where the networks reside.')
    argp.add_argument('--cvpn', type=str, default='no', help='Whether to provision networks for CVPN in.')
    args = argp.parse_args()
    region = args.region
    if args.cvpn == 'yes':
        cvpn = True
    else:
        cvpn = False

    output = {'code': 0, 'success': 'false'}
    output['data'] = {}

    if region in regionalNetworks:
        ssvpc = createSsVpc(region, cvpn)
        if ssvpc['code'] == 200:
            output['code'] = 200
            output['success'] = 'true'
            output['data'][0] = ssvpc['data']
            output['data'][1] = createvEdgeVpc(region)['data']
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
