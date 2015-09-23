#!/usr/bin/env python
#
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import os
import sys
import time
import pytest
import subprocess
import shutil

from halonutils.halonutil import *
from halonvsi.docker import *
from halonvsi.halon import *

import json
import httplib
import urllib

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

path = "/rest/v1/system"
data = ""

class myTopo(Topo):
    def build(self, hsts=0, sws=1, **_opts):

        self.hsts = hsts
        self.sws = sws

        host = self.addHost('h1')
        switch = self.addSwitch("s1")
        self.addLink('h1', 's1')

class systemTest(HalonTest):
    def setupNet(self):
        self.net = Mininet(topo=myTopo(hsts=NUM_HOSTS_PER_SWITCH,
                                       sws=NUM_OF_SWITCHES,
                                       hopts=self.getHostOpts(),
                                       sopts=self.getSwitchOpts()),
                                       switch=HalonSwitch,
                                       host=HalonHost,
                                       link=HalonLink,
                                       controller=None,
                                       build=True)

    def execute_request(self, http_method, request_data):
        s1 = self.net.switches[0]
        switch_ip = s1.cmd("python -c \"import socket; print socket.gethostbyname(socket.gethostname())\"")
        headers = {"Content-type": "application/json", "Accept": "text/plain"}
        conn = httplib.HTTPConnection(switch_ip, 8091)
        conn.request(http_method, path, request_data, headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response, data

    def call_system_get(self):
        info("\n########## Executing GET request on %s ##########\n" % path)

        # # Execute GET

        response, json_string = self.execute_request("GET", json.dumps(""))

        assert response.status == httplib.OK

        get_data = {}

        try:
            # A malformed json should throw an exception here
            get_data = json.loads(json_string)
        except:
            assert False

        # # Check data was received

        assert get_data
        assert type(get_data) is dict
        assert len(get_data) > 0

    def call_system_options(self):
        info("\n########## Executing OPTIONS request on %s ##########\n" % path)

        # # Execute OPTIONS

        response, json_string = self.execute_request("OPTIONS", json.dumps(""))

        assert response.status == httplib.OK

        # # Check expected options are correct

        # TODO change these to propper expected values after correct OPTIONS is implemented
        expected_allow = ["DELETE", "GET", "OPTIONS", "POST", "PUT"]
        response_allow = response.getheader("allow").split(", ")

        assert expected_allow == response_allow

        # TODO change these to propper expected values after correct OPTIONS is implemented
        expected_access_control_allow_methods = ["DELETE", "GET", "OPTIONS", "POST", "PUT"]
        response_access_control_allow_methods = response.getheader("access-control-allow-methods").split(", ")

        assert expected_access_control_allow_methods == response_access_control_allow_methods

    def call_system_put(self):
        info("\n########## Executing PUT request on %s ##########\n" % path)

        # # Get initial data

        response, pre_put_json_string = self.execute_request("GET", json.dumps(""))

        assert response.status == httplib.OK

        pre_put_get_data = {}

        try:
            # A malformed json should throw an exception here
            pre_put_get_data = json.loads(pre_put_json_string)
        except:
            assert False

        # # Execute PUT request

        put_data = pre_put_get_data['configuration']

        # Modify config keys
        put_data['hostname'] = 'test'
        put_data['dns_servers'].append("8.8.8.8")
        put_data['asset_tag_number'] = "tag"
        put_data['other_config'] = {"key1": "value1"}
        put_data['external_ids'] = {"id1": "value1"}

        response, json_string = self.execute_request("PUT", json.dumps({'configuration': put_data}))

        assert response.status == httplib.OK

        # # Get post-PUT data

        response, post_put_json_string = self.execute_request("GET", json.dumps(""))

        assert response.status == httplib.OK

        post_put_get_data = {}

        try:
            # A malformed json should throw an exception here
            post_put_get_data = json.loads(post_put_json_string)
        except:
            assert False

        # post-PUT data should be the same as pre-PUT data
        post_put_data = post_put_get_data['configuration']

        assert put_data == post_put_data

        # # Perform bad PUT request

        json_string = json.dumps({'configuration': put_data})
        json_string += ","

        response, json_string = self.execute_request("PUT", json_string)

        assert response.status == httplib.BAD_REQUEST

class Test_system:
    def setup (self):
        pass

    def teardown (self):
        pass

    def setup_class (cls):
        Test_system.test_var = systemTest()

    def teardown_class (cls):
        Test_system.test_var.net.stop()

    def setup_method (self, method):
        pass

    def teardown_method (self, method):
        pass

    def __del__ (self):
        del self.test_var

    def test_run (self):
        self.test_var.call_system_get()
        self.test_var.call_system_options()
        self.test_var.call_system_put()
