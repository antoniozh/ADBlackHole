#!/usr/bin/env python3 

import configparser 
# TODO argparser, custom config 
import argparse
import requests
import os
import bencode
import json

# _agent = "ADBlackHole"
_agent = "BlackHole"

api = None 
config = None 
monitor_path = None 

payload = {}

# Read API key from config.ini
def getConfig():
    global api, config, monitor_path
    config = configparser.ConfigParser()
    config.read("config.ini")
    api = config['Config']['API']
    monitor_path = config['Config']['path']

    payload['apikey'] = api 
    payload['agent'] = _agent

def testAPI():
    r = requests.get('http://api.alldebrid.com/v4/user', payload )
    return r.json()['status'] == 'success'

def poll():
    for f in os.listdir(monitor_path):
        toUpload = {}
        
        i = 0
        if f.endswith(".torrent"):
            # https://2.python-requests.org/en/master/user/quickstart/#more-complicated-post-requests
            # If you want, you can send strings to be received as files:

            # Apparently it's important to upload as an array with index
            toUpload['files[%d]' % i] = (f,  open(monitor_path + f, 'rb'), 'application/x-bittorrent')
            i += 1

    r = requests.post('https://api.alldebrid.com/v4/magnet/upload/file', params=payload, files=toUpload)
    response = r.json()
    open('dump_python.json', 'w').write(json.dumps(response, indent=4))

    if response['status'] != 'success':    
        raise RuntimeError()

def start():
    getConfig()
    if not testAPI():
        raise Exception("API key seems to be wrong")
    
    
    poll()

start()