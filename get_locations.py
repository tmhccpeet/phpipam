#!/usr/bin/env python3
import json
import csv
import http.client
import mimetypes

with open('config.json') as json_config_file:
    config = json.load(json_config_file)

conn = http.client.HTTPSConnection(config['server'])
payload = ''
headers = {
  'token': config['token'],
}
conn.request('GET', '/api/' + config['app'] + '/tools/locations/', payload, headers)
res = conn.getresponse()
data = res.read().decode('utf-8')

with open('data_file.csv', 'w', newline='', encoding='utf-8-sig') as data_file:
    csv_writer = csv.writer(data_file)

    # Use a counter for the headers
    count = 0
    	
    for item in json.loads(data)['data']:
        # Only for the 1st line write the header (keys)
        if count == 0:
            header = item.keys()
            csv_writer.writerow(header)
            count += 1
    
        csv_writer.writerow(item.values())
