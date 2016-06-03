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

from rest_utils import (
    get_switch_ip, execute_request, rest_sanity_check, login,
    get_server_crt, remove_server_crt
)
from swagger_test_utility import swagger_model_verification
from fakes import create_fake_vlan
from copy import deepcopy
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

base_vlan_data = {
    "configuration": {
        "name": "test",
        "id": 1,
        "description": "test vlan",
        "admin": ["up"],
        "other_config": {},
        "external_ids": {}
    }
}

test_vlan_data = {}
test_vlan_data["int"] = deepcopy(base_vlan_data)
test_vlan_data["string"] = deepcopy(base_vlan_data)
test_vlan_data["dict"] = deepcopy(base_vlan_data)
test_vlan_data["empty_array"] = deepcopy(base_vlan_data)
test_vlan_data["one_string"] = deepcopy(base_vlan_data)
test_vlan_data["multiple_string"] = deepcopy(base_vlan_data)
test_vlan_data["None"] = deepcopy(base_vlan_data)
test_vlan_data["boolean"] = deepcopy(base_vlan_data)

DEFAULT_BRIDGE = "bridge_normal"

switches = []
vlan_id = None
vlan_name = None
vlan_path = None
vlan = None


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy, PATH, vlan_id, vlan_name
    global vlan_path, vlan
    PATH = "/rest/v1/system/bridges"
    cookie_header = None
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(switches[0])
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    vlan_id = 1
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (PATH, DEFAULT_BRIDGE)
    vlan = "%s/%s/vlans/%s" % (PATH,
                               DEFAULT_BRIDGE,
                               vlan_name)
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
def sanity_check(topology):
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)
    create_fake_vlan(vlan_path,
                     SWITCH_IP,
                     vlan_name,
                     vlan_id)


def test_putexistingvlan(step, topology, netop_login, sanity_check):
    ops1 = topology.get("ops1")
    assert ops1 is not None
    step("container_id_test %s\n" % ops1.container_id)
    swagger_model_verification(ops1.container_id,
                               "/system/bridges/{pid}/vlans/{id}",
                               "PUT", base_vlan_data)
    data = deepcopy(base_vlan_data)
    data["configuration"]["name"] = vlan_name

    step("\n########## Executing PUT to %s ##########\n" % vlan_path)
    step("Testing Path: %s\n" % vlan_path)

    response_status, response_data = execute_request(
        vlan, "PUT", json.dumps(data), SWITCH_IP,
        xtra_header=cookie_header)

    assert response_status == http.client.OK, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing PUT to %s DONE "
         "##########\n" % vlan_path)


def test_putvlaninvalidname(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("string")
    data.pop("one_string")

    data["int"]["configuration"]["name"] = 1
    data["dict"]["configuration"]["name"] = {}
    data["empty_array"]["configuration"]["name"] = []
    data["multiple_string"]["configuration"]["name"] = ["test_vlan_1",
                                                        "test_vlan_2"]
    data["None"]["configuration"]["name"] = None
    data["boolean"]["configuration"]["name"] = True

    step("\n########## Executing POST test with bad \"name\" value "
         "##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"name\" as [%s] with value: %s\n" % (field,
                                                                  value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"name\" value DONE "
         "##########\n")


def test_putvlaninvalidid(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("int")

    data["string"]["configuration"]["id"] = "id"
    data["dict"]["configuration"]["id"] = {}
    data["empty_array"]["configuration"]["id"] = []
    data["one_string"]["configuration"]["id"] = ["id"]
    data["multiple_string"]["configuration"]["id"] = ["test_vlan_1",
                                                      "test_vlan_2"]
    data["None"]["configuration"]["id"] = None
    data["boolean"]["configuration"]["id"] = True

    step("\n########## Executing POST test with bad \"id\" value "
         "##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"id\" as [%s] with value: %s\n" % (field,
                                                                value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"id\" value DONE "
         "##########\n")


def test_putvlaninvaliddescription(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("string")
    data.pop("one_string")

    data["int"]["configuration"]["description"] = 1
    data["dict"]["configuration"]["description"] = {}
    data["empty_array"]["configuration"]["description"] = []
    data["multiple_string"]["configuration"]["description"] = \
        ["test_vlan_1", "test_vlan_2"]
    data["None"]["configuration"]["description"] = None
    data["boolean"]["configuration"]["description"] = True

    step("\n########## Executing PUT test with bad \"description\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"description\" as [%s] with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing PUT test with bad \"description\" value "
         "DONE ##########\n")


def test_putvlaninvalidadmin(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("dict")

    data["int"]["configuration"]["admin"] = 1
    data["string"]["configuration"]["admin"] = "admin"
    data["empty_array"]["configuration"]["admin"] = []
    data["one_string"]["configuration"]["admin"] = ["admin"]
    data["multiple_string"]["configuration"]["admin"] = ["test_vlan_1",
                                                         "test_vlan_2"]
    data["None"]["configuration"]["admin"] = None
    data["boolean"]["configuration"]["admin"] = True

    step("\n########## Executing PUT test with bad \"admin\" value "
         "##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"admin\" as %s with value: %s\n" % (field,
                                                                 value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing PUT test with bad \"admin\" value DONE "
         "##########\n")


def test_putvlaninvalidotherconfig(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("dict")

    data["int"]["configuration"]["other_config"] = 1
    data["string"]["configuration"]["other_config"] = "other_config"
    data["empty_array"]["configuration"]["other_config"] = []
    data["one_string"]["configuration"]["other_config"] = ["other_config"]
    data["multiple_string"]["configuration"]["other_config"] = \
        ["test_vlan_1", "test_vlan_2"]
    data["None"]["configuration"]["other_config"] = None
    data["boolean"]["configuration"]["other_config"] = True

    step("\n########## Executing PUT test with bad \"other_config\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"other_config\" as [%s] with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing PUT test with bad \"other_config\" "
         "value DONE ##########\n")


def test_putvlaninvalidexternalids(topology, step, netop_login, sanity_check):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("dict")

    data["int"]["configuration"]["external_ids"] = 1
    data["string"]["configuration"]["external_ids"] = "external_ids"
    data["empty_array"]["configuration"]["external_ids"] = []
    data["one_string"]["configuration"]["external_ids"] = ["external_ids"]
    data["multiple_string"]["configuration"]["external_ids"] = \
        ["test_vlan_1", "test_vlan_2"]
    data["None"]["configuration"]["external_ids"] = None
    data["boolean"]["configuration"]["external_ids"] = True

    step("\n########## Executing PUT test with bad \"external_ids\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"external_ids\" as %s with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan, "PUT", json.dumps(value), SWITCH_IP,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing PUT test with bad \"external_ids\" value "
         "DONE ##########\n")
