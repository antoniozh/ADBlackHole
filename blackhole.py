#!/usr/bin/env python3

import configparser
# TODO argparser, custom config
import argparse
import requests
import os
import json
import shutil
import logging
from time import sleep
logger = None

# _agent = "ADBlackHole"
_agent = "BlackHole"
_MAX_TORRENT_COUNT = 5

api = None
config = None
monitor_path = None
crawl_path = None
parser = None 
args = None 

torrent_list = []

payload = {}

# Read API key from config.ini

api_url = 'http://api.alldebrid.com/v4/'

def getConfig():
    global api, config, monitor_path, crawl_path, torrent_list, logger 

    logging.basicConfig()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.info("Started monitoring...")

    config = configparser.ConfigParser()
    config.read(args.config)
    api = config['Config']['API']
    monitor_path = config['Config']['path']
    
    crawl_path = args.crawl

    if os.path.isfile("torrent_list.txt"):
        f = open('torrent_list.txt', 'r')
        torrent_list = list(map(lambda x: int(x), f.readlines()))
    payload['apikey'] = api
    payload['agent'] = _agent

def createFolders():
    if not os.path.isdir(monitor_path):
        os.mkdir(monitor_path)
    if not os.path.isdir(crawl_path):
        os.mkdir(crawl_path)
    if not os.path.isdir(crawl_path + '/added/'):
        os.mkdir(crawl_path + '/added/')

def testAPI():
    r = requests.get('user', payload)
    return r.json()['status'] == 'success'

def poll():
    toUpload = {}
    # TODO: upload magnet links too 
    magnetLinks = {}
    i = 0
    for f in os.listdir(monitor_path):
        # TODO: Get active torrents and add as many as allowed
        # open items
        if f.endswith(".torrent") and i < _MAX_TORRENT_COUNT:
            # https://2.python-requests.org/en/master/user/quickstart/#more-complicated-post-requests
            # If you want, you can send strings to be received as files:

            # Apparently it's important to upload as an array with index
            toUpload['files[%d]' % i] = (
                f,  open(monitor_path + f, 'rb'), 'application/x-bittorrent')

            logger.info("Added torrent: %s to AllDebrid server" % ( f ))
            i += 1

    r = requests.post(
        api_url + 'magnet/upload/file', params=payload, files=toUpload)

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
            torrent_list.extend(
                map(lambda x: x['id'],  response['data']['files']))
            for file in response['data']['files']:
                filename = file['file']
                if os.path.isfile(monitor_path + filename):
                    try:
                        shutil.move(monitor_path + filename,
                                    monitor_path + "added/" + filename)
                    except PermissionError as e:
                        # TODO: Logger
                        logger.error(e)
                        pass

    # Get count
    r = requests.get('api_url' + 'magnet/status', payload)
    r.raise_for_status()
    response = r.json()

    if response['status'] == 'success':
        parseMagnets(response['data']['magnets'])

    # update torrent_list
    with open('torrent_list.txt', 'w') as f:
        f.writelines(map(lambda x: str(x) + "\n", torrent_list))


def parseMagnets(magnetList: list):
    count = 0

    for magnet in magnetList:
        code = magnet['statusCode']

        if code > 0 and code < 1:
            count += 1

        # Ready to download
        elif code == 4 and magnet['id'] in torrent_list:
            # Create crawljob for jdownloader
            # https://github.com/cooolinho/jdownloader-folderwatch/blob/master/crawljob-examples/download-archive.crawljob
            f = open("%s/%s.crawljob" % (crawl_path,  str(magnet['id'])), 'w')
            f.writelines(generateCrawlJob(magnet))
            torrent_list.remove(magnet['id'])
            f.close()
            logger.info('Wrote %s.crawljob to %s' % ( str(magnet['id'], crawl_path )  ))

            # Delete from list
            new_payload = payload.copy() 
            new_payload['id'] = magnet['id']
            r = requests.get('api_url' + "magnet/delete", new_payload ) 

            r.raise_for_status()
            if r.json()['status'] == 'success': 
                logger.info('Deleted %s '  % magnet['filename'])
            else:
                logger.warn('Could not delete %s from AllDebrid server. %s' % ( magnet['filename'], r.json() )  )
            
    return count

# Returns list str


def generateCrawlJob(magnet: dict):
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

    if parser.path_download != None:
        lines.append("downloadFolder=%s" % parser.path_download)
    
    return map(lambda s: s + "\n", lines)

def start():
    getConfig()
    createFolders()
    if not testAPI():
        raise Exception("API key seems to be wrong")
    while True: 
        poll()
        sleep(60)

def setupArgs():
    global parser, args
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="Path of the config.ini file", default="config.ini")
    parser.add_argument("-m", "--monitor", help="Path of the directory the script should monitor", default="./torrents/")
    parser.add_argument("-C", "--crawl", help="Path of the directory the crawljobs will be written into", default="./crawl/")
    parser.add_argument("--api", help="API Token for alldebrid")
    parser.add_argument("-p", "--path-download", help="Path of the download directory the crawljobs should point to" )
    args = parser.parse_args()

    start()

setupArgs()