#!/usr/bin/env python3 

import configparser 
# TODO argparser, custom config 
import argparse
import requests
import os
import bencode
import json
import shutil
import logging

logger = logging.getLogger(__name__)

# _agent = "ADBlackHole"
_agent = "BlackHole"
_MAX_TORRENT_COUNT = 5

api = None 
config = None 
monitor_path = None 
crawl_path = None

torrent_list = [] 

payload = {}

# Read API key from config.ini
def getConfig():
    global api, config, monitor_path, crawl_path    
    config = configparser.ConfigParser()
    config.read("config.ini")
    api = config['Config']['API']
    monitor_path = config['Config']['path']
    crawl_path = config['Config']['crawl_path']

    # TODO add added folder

    if os.path.isfile("torrent_list.txt"):
        f = open('torrent_list.txt', 'r')
        torrent_list = map( lambda x : int(x)  ,f.readlines() )

    payload['apikey'] = api 
    payload['agent'] = _agent

def testAPI():
    r = requests.get('http://api.alldebrid.com/v4/user', payload )
    return r.json()['status'] == 'success'

def poll():
    # Get count 
    r = requests.get('https://api.alldebrid.com/v4/magnet/status', payload)
    r.raise_for_status()
    response = r.json()

    if response['status'] == 'success':
        parseMagnets( response['data']['magnets'] )


    toUpload = {}
    i = 0
    for f in os.listdir(monitor_path):
        # TODO: Get active torrents and add as many as allowed
        # open items
        if f.endswith(".torrent") and i < _MAX_TORRENT_COUNT:
            # https://2.python-requests.org/en/master/user/quickstart/#more-complicated-post-requests
            # If you want, you can send strings to be received as files:

            # Apparently it's important to upload as an array with index
            toUpload['files[%d]' % i] = (f,  open(monitor_path + f, 'rb'), 'application/x-bittorrent')
            i += 1

    

    r = requests.post('https://api.alldebrid.com/v4/magnet/upload/file', params=payload, files=toUpload)

    # Close items 
    for toClose in toUpload.values():
        toClose[1].close()

    response = r.json()

    r.raise_for_status()
    # Logging 
    # open('dump_python.json', 'w').write(json.dumps(response, indent=4))

    if response['status'] == 'success':    
    # Extend torrent list by added torrents
        if len(toUpload) > 0:
            torrent_list.extend(map(lambda x: x['id'],  response['data']['files']))
            with open('torrent_list.txt', 'w') as f:
                f.writelines(map(lambda x : str(x) + "\n", torrent_list))
            for file in response['data']['files']:
                filename = file['file']
                if os.path.isfile(monitor_path + filename ):
                    try: 
                        shutil.move( monitor_path + filename , monitor_path + "added/" + filename )
                    except PermissionError as e:
                        # TODO: Logger
                        logger.error(e)
                        pass

def parseMagnets( magnetList : list ):
    count = 0

    for magnet in magnetList:
        code = magnet['statusCode']

        if code > 0 and code < 1:
            count += 1

        # Ready to download
        elif code == 4:
            # Create crawljob for jdownloader
            # https://github.com/cooolinho/jdownloader-folderwatch/blob/master/crawljob-examples/download-archive.crawljob 
            f = open( "%s/%s.crawljob" % ( crawl_path ,  str(magnet['id']) ), 'w')
            f.writelines(generateCrawlJob(magnet))
            f.close()

    return count

# Returns list str 
def generateCrawlJob(magnet : dict):
    lines = [
        "packageName=%s" % magnet['filename'],
        # dirty af 
        "text=%s" % str(list(map(lambda x: x['link'], magnet['links']))),
        # jDownloader settings
        "enabled=true",
        "autoStart=TRUE",
        "forcedStart=TRUE",
        "autoConfirm=TRUE",
        # archive settings
        "extractAfterDownload=TRUE"
    ]
    
    return map( lambda s : s + "\n", lines )

def start():
    getConfig()
    if not testAPI():
        raise Exception("API key seems to be wrong")
    
    poll()

start()