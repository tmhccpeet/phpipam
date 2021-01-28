#!/usr/bin/env python3
""" This script parses a CSV file and imports them into phpIPAM using
API callx.

This file parses a UTF8 encoded and signed CSV file containing
location ('sites') information and 
imports them into phpIPAM.

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

def main():
    # Read input arguments
    argp = argparse.ArgumentParser(description = 'Import locations based on CSV input.')
    argp.add_argument('infile', type=str, nargs=1, help='UTF8 encoded input CSV file')
    args = argp.parse_args()

    # Clean library of locations
    locations = {}

    url = "https://phpipam.hcch.com/api/PeetScript/tools/locations/"
    headers = {
        'token': 'dvQGBJIh14g17wgtzVLiZYUhFffo-yzu',
        'Content-Type': 'text/plain'
    }

    # Open infile
    with open(args.infile[0], 'r', encoding='utf-8-sig') as data_file:
        csv_reader = csv.DictReader(data_file)

        for line in csv_reader:
            payload = ""
            name = ""
            for key, value in line.items():
                if value == 'null':
                    value = ''
                else:
                    value = urllib.parse.quote(value)
                payload = payload + f"&{key}={value}"
                if key == "name":
                    name = value

            r = requests.request("POST", url, headers=headers, data=payload)
            response = json.loads(r.text)
            print(f"{name}: {response['success']}")
            if 'message' in response:
                print(response['message'])

if __name__ == "__main__":
    main()
