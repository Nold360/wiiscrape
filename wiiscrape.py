#!/usr/bin/env python3
# Badly Written nus.cdn.shop.wii.com Scraper
#
# - Reads database.xml & downloads every title for every region and in any version
# - Dump will be saved to DOWNLOAD_PATH
# - Downloads are Threaded with a maximum of MAX_THREADS
#
# Dumpsize is about 21GB
# 
import xml.etree.ElementTree as ET
from binascii import hexlify
from struct import unpack
from threading import Thread
from time import sleep

import urllib.request
import shutil
import os
import re

# Config:
DOWNLOAD_PATH = "./wiinus"
MAX_THREADS = 5
# /Config

NUS_BASE_URL = "http://nus.cdn.shop.wii.com/ccs/download/"
UPDATING_USER_AGENT = "wii libnup/1.0"
VIRTUAL_CONSOLE_USER_AGENT = "libec-3.0.7.06111123"
WIICONNECT24_USER_AGENT = "WiiConnect24/1.0FC4plus1 (build 061114161108)"
SHOPPING_USER_AGENT = "Opera/9.00 (Nintendo Wii; U; ; 1038-58; Wii Shop Channel/1.0; en)"

class NUSTitle(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.name = None
        self.ticket = None
        self.titleID = None
        self.ticket = "false"
        self.regions = []
        self.versions = [ "latest" ]
        self.titleIDlist = []
        self.region_regex = re.compile('xx$')

        self.debug = False

    def download_file(self, titleID, filename, size=None):
        url = NUS_BASE_URL + titleID + "/" + filename
        req = urllib.request.Request(url, data=None, headers = { 'User-Agent': UPDATING_USER_AGENT })

        path = DOWNLOAD_PATH + "/" + titleID + "/" + filename
        if self.debug:
            print("Downloading: " + url)

        try:
            with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("  - Failed downloading: %s\n  - %s" % (url, str(e)))
            return False
        return True

    def download_content(self, titleID, version):
        if "latest" in version:
            tmdfile = "/tmd"
        else:
            tmdfile = "/tmd." + version
        filename = DOWNLOAD_PATH + "/" + titleID + "/" + tmdfile

        with open(filename, "rb") as tmd:
            # Number of Contents
            tmd.seek(0x1DE)
            count = unpack(">H", tmd.read(2))[0]
            #print("Content count: " + str(count))

            # Contents
            tmd.seek(0x1E4)
            # Loop over every content
            
            content = []
            if self.debug:
                print("Downloading Content:")
            for i in range(count):
                # This will extract content id, index, type, size and SHA1 hash and store them in a list
                # https://docs.python.org/3/library/struct.html#format-characters ("IHHQ": 4, 2, 2, 8)
                data = [a for a in unpack(">IHHQ", tmd.read(16))]
                data.append(hexlify(tmd.read(20)))

                if self.debug:
                    print("  - Content: %i/%i [%s] - %i Bytes" % ((i+1), count, str("%08X" % data[0]), data[3]))
                    print(NUS_BASE_URL + "/" + titleID + "/" + str("%08X" % data[0]))
                self.download_file(titleID, str("%08X" % data[0]).lower())
                

    def run(self):
        self.gen_titleIDlist()
        self.gen_folders()
        for ver in self.versions:
            # -1 = latest
            for titleID in self.titleIDlist:
                if self.debug:
                    print("\n + Downloading %s(%s) v%s" % (self.name, titleID, ver))

                # Download Latest Version

                # try to get tmd
                if "latest" in ver:
                    tmdfile = "tmd"
                else:
                    tmdfile = "tmd." + ver
                if self.download_file(titleID, tmdfile):
                    # Download cetk / ticket
                    if "true" in self.ticket:
                        if self.debug:
                           print("  - Downloading Ticket..")
                        self.download_file(titleID, "cetk")
                    elif self.debug:
                        print("  - No Ticket Available")

                    # Download all Parts
                    self.download_content(titleID, ver)

    def gen_folders(self):
        for title in self.titleIDlist:
            title_dir = DOWNLOAD_PATH + "/" + title
            try:
                os.stat(title_dir)
            except:
                os.mkdir(title_dir) 
    
    def gen_titleIDlist(self):
        if self.region_regex.search(self.titleID) is not None:
            #print(self.titleID)
            for reg in self.regions:
                title = re.sub(self.region_regex, reg.lower(), self.titleID)
                self.titleIDlist.append(title.lower()) 
        else:
            self.titleIDlist = [ self.titleID ]


tree = ET.parse('database.xml')
root = tree.getroot()

# Get all Regions first
regions = []
print("Loading Regions...")
for child in root:
    if 'REGIONS' in child.tag:
        print("Regions: ")
        for sub in child:
            regcode = re.match(r'[0-9A-F]{2}', sub.text)
            print(regcode.group(0))
            regions.append(regcode.group(0))
        print("------------------\n")

if regions == []:
    raise Exception("Error: Couldn't load regions from database.xml")

# Create list of all titles as NUSTitle objects
title_list = []
version_regex = re.compile('\d+')
print("Creating list of all titles...")
for child in root:
    if 'WW' in child.tag \
    or 'VC' in child.tag \
    or 'IOS' in child.tag \
    or 'SYS' in child.tag:
       this_title = NUSTitle() 
    else:
        continue

    for sub in child:
        if sub.tag == 'region':
            for reg in sub.text.split(','):
                this_title.regions.append(regions[int(reg)])
        elif sub.tag == "name":
            this_title.name = sub.text
        elif sub.tag == "titleID":
            # If XX$ in titleID
            this_title.titleID = sub.text.lower()
        elif "version" in sub.tag:
            for ver in version_regex.findall(sub.text):
                this_title.versions.append(ver)
        elif "ticket" in sub.tag:
            this_title.ticket = sub.text
    title_list.append(this_title)

print("Starting Download..")
# Create Download Threads from NUSTitles

threads = []
title_num = 0
while title_num < len(title_list):
    if len(threads) < MAX_THREADS:
        print("Starting Download Thread - %s[%s] - %i/%i" % \
            (title_list[title_num].name, title_list[title_num].titleID, \
            (title_num+1), len(title_list)))
        title_list[title_num].start()
        threads.append(title_list[title_num])
        title_num += 1
    else:
        for thread in threads:
            if not thread.isAlive():
                print("Finished Download Thread - %s[%s]" % (thread.name, thread.titleID))
                threads.remove(thread)
        sleep(1)
        
