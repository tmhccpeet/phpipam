#!/usr/bin/env python3
import argparse
import json, csv
import http.client, mimetypes

import pprint

parser = argparse.ArgumentParser(description = 'Update PHPipam lcations based on CSV input.')
parser.add_argument('csv', help='UTF8 encoded CSV file with actions and updates')
args = parser.parse_args()

with open('config.json') as json_config_file:
    config = json.load(json_config_file)

# Start with a clear dictionary
data = {}

with open(args.csv, 'r', encoding='utf-8-sig') as data_file:
    csv_reader = csv.DictReader(data_file)
    for line in csv_reader:
        key = line['id']
        data[key] = line
 
# pp = pprint.PrettyPrinter(indent=4)
# pp.pprint(data)
# 
# for location in data:
#     pp.pprint(location)
#     print('\n')
# 
#     # Use a counter for the headers
#     count = 0
#     	
#     for item in json.loads(data)['data']:
#         # Only for the 1st line write the header (keys)
#         if count == 0:
#             header = item.keys()
#             csv_writer.writerow(header)
#             count += 1
#     
#         csv_writer.writerow(item.values())
# 
# 
# 
# conn = http.client.HTTPSConnection(config['server'])
# payload = ''
# headers = {
#   'token': config['token'],
# }
# conn.request('PATCH', '/api/' + config['app'] + '/tools/locations/', payload, headers)
# res = conn.getresponse()
# data = res.read().decode('utf-8')
# 
