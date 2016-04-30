#!/usr/bin/env python
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

from opsvsi.docker import *
from opsvsi.opsvsitest import *

import json
import httplib

from opsvsiutils.restutils.utils import execute_request, login, \
    get_switch_ip, rest_sanity_check, get_container_id, get_json
from copy import deepcopy
from opsvsiutils.restutils.swagger_test_utility import \
    swagger_model_verification

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

ROUTE_PREFIX = "192.168.0.0/16"
HTML_ROUTE_PREFIX = "192.168.0.0%2F16"

base_route_data = {
    "configuration": {
        "address_family": "ipv4",
        "distance": 1,
        "from": "static",
        "metric": 0,
        "prefix": "192.168.0.0/16",
        "sub_address_family": "unicast"
    }
}


class myTopo(Topo):
    def build(self, hsts=0, sws=1, **_opts):
        self.hsts = hsts
        self.sws = sws
        self.switch = self.addSwitch("s1")


@pytest.fixture
def netop_login(request):
    request.cls.test_var.cookie_header = login(request.cls.test_var.SWITCH_IP)


class DynamicCategoryTest (OpsVsiTest):
    def setupNet(self):
        self.net = Mininet(topo=myTopo(hsts=NUM_HOSTS_PER_SWITCH,
                                       sws=NUM_OF_SWITCHES,
                                       hopts=self.getHostOpts(),
                                       sopts=self.getSwitchOpts()),
                           switch=VsiOpenSwitch, host=None, link=None,
                           controller=None, build=True)

        self.SWITCH_IP = get_switch_ip(self.net.switches[0])
        self.PATH = "/rest/v1/system/vrfs/vrf_default/routes"
        self.cookie_header = None

    def create_static_route(self):
        info("\n########## Test to Validate Create Static Route "
             "##########\n")
        data = deepcopy(base_route_data)
        data["from"] = "static"
        status_code, response_data = execute_request(
            self.PATH, "POST", json.dumps(data),
            self.SWITCH_IP, xtra_header=self.cookie_header)

        assert status_code == httplib.CREATED, \
            "Unexpected status code. Received: %s Response data: %s " % \
            (status_code, response_data)
        info("### Static route created ###\n")

        # Verify data
        new_path = self.PATH + "/" + data["from"] + "/" + HTML_ROUTE_PREFIX
        status_code, response_data = execute_request(
            new_path, "GET", None, self.SWITCH_IP,
            xtra_header=self.cookie_header)

        assert status_code == httplib.OK, "Failed to query route"
        json_data = get_json(response_data)

        assert json_data["configuration"] == base_route_data["configuration"], \
            "Configuration data is not equal that posted data"
        info("### Configuration data validated ###\n")

        info("\n########## End Test to Validate Create Static Route "
             "##########\n")

    def create_connected_route(self):
        info("\n########## Test create connected route ##########\n")
        data = deepcopy(base_route_data)
        data["from"] = "connected"
        status_code, response_data = execute_request(
            self.PATH, "POST", json.dumps(data),
            self.SWITCH_IP, xtra_header=self.cookie_header)

        assert status_code == httplib.BAD_REQUEST, \
            "Unexpected status code. Received: %s Response data: %s " % \
            (status_code, response_data)
        info("### Route cannot be created  ###\n")

        info("\n########## End Test create connected route ##########\n")


class Test_DynamicCategory:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_DynamicCategory.test_var = DynamicCategoryTest()
        rest_sanity_check(cls.test_var.SWITCH_IP)
        cls.container_id = get_container_id(cls.test_var.net.switches[0])

    def teardown_class(cls):
        Test_DynamicCategory.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_run_create_static_route(self, netop_login):
        self.test_var.create_static_route()
        swagger_model_verification(self.container_id,
                                   "/system/vrfs/{pid}/routes",
                                   "POST",
                                   base_route_data)

    def test_run_create_connected_route(self, netop_login):
        self.test_var.create_connected_route()
