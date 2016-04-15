# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import ssl
import os
import json
import imp
import sys

try:
    imp.find_module('websocket')
    import websocket
except ImportError:
    print "Please install websocket-client first."
    exit()

# Command line args
IP_ADDR_OPT = '-i'


def main():
    cmd_args = {}
    get_cmd_args(cmd_args)

    if IP_ADDR_OPT not in cmd_args:
        handle_usage_error("IP address not defined.")

    connect_to_server(cmd_args[IP_ADDR_OPT], get_ssl_opts())


def get_cmd_args(cmd_args):
    # Get the total number of args passed
    total_args = len(sys.argv)

    # Get the arguments list
    cmdargs = sys.argv

    if (total_args < 3) or (total_args % 2 != 1):
        handle_usage_error("Invalid number of args.")

    for index, arg in enumerate(cmdargs):
        print arg
        if arg == IP_ADDR_OPT:
            cmd_args[IP_ADDR_OPT] = cmdargs[index + 1]


def get_ssl_opts():
    src_path = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(src_path, 'server.crt')

    sslopt = {"cert_reqs": ssl.CERT_REQUIRED,
              "check_hostname": False,
              "ca_certs": src_file,
              "ssl_version": ssl.PROTOCOL_SSLv23}

    return sslopt


def connect_to_server(ip_address, sslopt):
    ws = websocket.WebSocket(sslopt=sslopt)
    ws.connect("wss://%s/rest/v1/ws/notifications" % ip_address)

    while True:
        parsed = json.loads(ws.recv())
        print json.dumps(parsed, indent=4)


def handle_usage_error(error):
    print error
    print_usage()
    exit()


def print_usage():
    print "Usage: python wsclient.py -i WS_SERVER_IP_ADDRESS"


if __name__ == "__main__":
    main()
