#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Retrospective update of Domoticz with Withings data ON DB LEVEL. BE CAREFULL!"""

import os
import sys
import time
import sqlite3
import requests
import re
import argparse
from datetime import datetime


_AUTHOR_ = 'dynasticorpheus@gmail.com'
_VERSION_ = "0.2.0"

TMPID = 12
CO2ID = 35

URL_DATA = "https://healthmate.withings.com/index/service/v2/measure"
URL_AUTH = "https://account.withings.com/connectionuser/account_login?appname=my2&appliver=c7726fda&r=https%3A%2F%2Fhealthmate.withings.com%2Fhome"
URL_ASSO = "https://healthmate.withings.com/index/service/association"

parser = argparse.ArgumentParser(description='Withings WS-50 Syncer by dynasticorpheus@gmail.com')
parser.add_argument('-u', '--username', help='username (email) in use with account.withings.com', required=True)
parser.add_argument('-p', '--password', help='password in use with account.withings.com', required=True)
parser.add_argument('-c', '--co2', help='co2 idx', type=int, required=True)
parser.add_argument('-t', '--temperature', help='temperature idx', type=int, required=True)
parser.add_argument('-d', '--database', help='fully qualified name of database-file', required=True)
parser.add_argument('-n', '--noaction', help='do not update database', action='store_true', required=False)
args = parser.parse_args()

AUTH_DATA = "email=" + args.username + "&is_admin=&password=" + args.password

s = requests.Session()
end = int(time.time())

print
print "Withings WS-50 Syncer Version " + _VERSION_
print

if os.path.exists(args.database):
    print "[-] Database " + args.database
else:
    print "[-] Database not found " + args.database
    print
    sys.exit()

print "[-] Authenticating at account.withings.com"

try:
    response = s.request("POST", URL_AUTH, data=AUTH_DATA)
except Exception:
    print "[-] Authenticating failed, exiting"
    sys.exit()

d = s.cookies.get_dict()
accountid = re.sub("[^0-9]", "", str(re.search('(?<=accountId)(.*)', response.content)))
payload = "accountid=" + str(accountid) + "&action=getbyaccountid&appliver=c7726fda&appname=my2&apppfm=web&enrich=t&sessionid=" + d['session_key'] + "&type=-1"
response = s.request("POST", URL_ASSO, data=payload)
r = response.json()
deviceid = r['body']['associations'][0]['deviceid']

conn = sqlite3.connect(args.database, timeout=60)
c = conn.cursor()

for row in c.execute('select max(Date) from Meter where DeviceRowID=' + str(args.co2)):
    if row[0] is None:
        START = 0
    else:
        dt_obj = datetime.strptime(str(row[0]), "%Y-%m-%d %H:%M:%S")
        START = int(time.mktime(dt_obj.timetuple())) + 1

BASE = "action=getmeashf&appliver=82dba0d8&appname=my2&apppfm=web&deviceid=" + str(deviceid) + "&enddate=" + \
    str(end) + "&sessionid=" + d['session_key'] + "&startdate=" + str(START) + "&meastype="

if row[0] is None:
    print "[-] Downloading complete data set"
else:
    print "[-] Downloading data newer than " + str(row[0])

try:
    payload = BASE + str(CO2ID)
    r2 = s.request("POST", URL_DATA, data=payload)
    payload = BASE + str(TMPID)
    r3 = s.request("POST", URL_DATA, data=payload)
except Exception:
    print "[-] Data download failed, exiting"
    sys.exit()

data = r2.json()
data2 = r3.json()

try:
    count = 0
    for item in data['body']['series']:
        for item2 in reversed(item['data']):
            print('[-] INSERT INTO Meter VALUES (' + str(args.co2) + ',' + str(item2['value']) + ',0,' + "'" + time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(item2['date'])) + "'" + ')')
            if args.noaction is not True:
                c.execute('INSERT INTO Meter VALUES (' + str(args.co2) + ',' + str(item2['value']) + ',0,' + "'" + time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(item2['date'])) + "'" + ')')
            count = count + 1
            sys.stdout.write("\033[F")
            sys.stdout.write("\033[K")
except Exception:
    print "[-] CO2 update failed, exiting"
    conn.close()
    sys.exit()


print "[-] Updating database with " + str(count) + " CO2 measurements" + " [" + str(not args.noaction).upper() + "]"

try:
    count = 0
    for item in data2['body']['series']:
        for item2 in reversed(item['data']):
            print('[-] INSERT INTO Temperature VALUES (' + str(args.temperature) + ',' + str(item2['value']) + ',0.0,0,0,0.0,0.0,' + "'" + time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(item2['date'])) + "'" + ')')
            if args.noaction is not True:
                c.execute('INSERT INTO Temperature VALUES (' + str(args.temperature) + ',' + str(item2['value']) + ',0.0,0,0,0.0,0.0,' + "'" + time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(item2['date'])) + "'" + ')')
            count = count + 1
            sys.stdout.write("\033[F")
            sys.stdout.write("\033[K")
except Exception:
    print "[-] TEMPERATURE update failed, exiting"
    conn.close()
    sys.exit()

print "[-] Updating database with " + str(count) + " TEMPERATURE measurements" + " [" + str(not args.noaction).upper() + "]"

if args.noaction is not True:
    print "[-] Committing and closing database"
    try:
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()

print