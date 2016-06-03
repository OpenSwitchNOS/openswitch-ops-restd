# -*- coding: utf-8 -*-
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
##########################################################################

from pytest import fixture


import json
import http.client

from rest_utils_ft import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    get_server_crt, remove_server_crt, create_test_port, PORT_DATA
)
from swagger_test_utility import swagger_model_verification


from os import environ
from time import sleep

# Topology definition. the topology contains two back to back switches
# having four links between them.


TOPOLOGY = """
# +-------+     +-------+
# |  ops1  <----->  hs1  |
# +-------+     +-------+

# Nodes
[type=openswitch name="Switch 1"] ops1
[type=oobmhost name="Host 1"] hs1

# Ports
[force_name=oobm] ops1:sp1

# Links
ops1:sp1 -- hs1:1
"""


SWITCH_IP = None
cookie_header = None
proxy = None
PATH = None
PORT_PATH = None


NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

switches = []


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy
    cookie_header = None
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(switches[0])
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switches[0])
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None
        remove_server_crt()

    request.addfinalizer(cleanup)


@fixture(scope="module")
def setup_test(topology):
    global PATH, PORT_PATH
    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/Port1"
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)
    status_code, response = create_test_port(SWITCH_IP)
    assert status_code == http.client.CREATED, \
        "Port not created. Response %s" % response


def query_all_ports(step):
    step("\n########## Test to Validate first GET all Ports request"
         "##########\n")

    status_code, response_data = execute_request(
        PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert \
        status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned: %s ###\n" % response_data)

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    assert len(json_data) > 0, "Wrong ports size %s " % len(json_data)
    step("### There is at least one port  ###\n")

    assert \
        PORT_PATH in json_data, "Port is not in data. Data returned is:" \
        " %s" % response_data[0]
    step("### Port is in list  ###\n")

    step("\n########## End Test to Validate first GET all Ports request"
         "##########\n")


def query_port(step):
    step("\n########## Test to Validate first GET single Port request"
         "##########\n")

    status_code, response_data = execute_request(
        PORT_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert \
        status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned: %s ###\n" % response_data)

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    assert \
        json_data["configuration"] is not None, "configuration key is not" \
        " present"
    assert \
        json_data["statistics"] is not None, "statistics key is not present"
    assert json_data["status"] is not None, "status key is not present"
    step("### Configuration, statistics and status keys present ###\n")

    assert \
        json_data["configuration"] == PORT_DATA["configuration"], \
        "Configuration data is not equal that posted data"
    step("### Configuration data validated ###\n")

    step("\n########## End Test to Validate first GET single Port request"
         "##########\n")


def query_non_existent_port(step):
    step("\n########## Test to Validate first GET Non-existent Port"
         " request  ##########\n")

    new_path = PATH + "/Port2"
    status_code, response_data = execute_request(
        new_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert \
        status_code == http.client.NOT_FOUND, "Wrong status code %s " \
        % status_code
    step("### Status code is NOT FOUND ###\n")

    step("\n########## End Test to Validate first GET Non-existent Port"
         " request ##########\n")


def test_ops_restd_ft_ports_get(topology, step, netop_login, setup_test):
    global switches
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    query_all_ports(step)
    query_port(step)
    query_non_existent_port(step)
    step("container_id_test %s\n" % switches[0].container_id)
    swagger_model_verification(switches[0].container_id, "/system/ports/{id}",
                               "GET_ID", PORT_DATA)
