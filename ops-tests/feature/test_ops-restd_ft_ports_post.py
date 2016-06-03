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
    execute_request, login, get_switch_ip, rest_sanity_check,
    PORT_DATA, execute_port_operations, get_server_crt,
    remove_server_crt
)
from swagger_test_utility import swagger_model_verification

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

switches = []


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy, PATH, PORT_PATH, PATH_INT
    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/Port1"
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
def sanity_check(topology):
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)


def create_port_with_depth(step):
    step("\n########## Test to Validate Create "
         "Port with depth ##########\n")
    status_code, response_data = execute_request(
        PATH + "?depth=1", "POST", json.dumps(PORT_DATA),
        SWITCH_IP, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Unexpected status code. Received: %s Response data: %s " % \
        (status_code, response_data)
    step("### Port not created. Status code is 400 BAD REQUEST ###\n")

    step("\n########## End Test to Validate Create Port with depth "
         "##########\n")


def create_port(step):
    step("\n########## Test to Validate Create Port ##########\n")
    status_code, response_data = execute_request(
        PATH, "POST", json.dumps(PORT_DATA), SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.CREATED, \
        "Error creating a Port. Status code: %s Response data: %s " % \
        (status_code, response_data)
    step("### Port Created. Status code is 201 CREATED  ###\n")

    # Verify data
    status_code, response_data = execute_request(
        PORT_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Failed to query added Port"
    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    assert json_data["configuration"] == PORT_DATA["configuration"], \
        "Configuration data is not equal that posted data"
    step("### Configuration data validated ###\n")

    step("\n########## End Test to Validate Create Port ##########\n")


def create_same_port(step):
    step("\n########## Test create same port ##########\n")
    status_code, response_data = execute_request(
        PORT_PATH, "POST", json.dumps(PORT_DATA), SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Validation failed, is not sending Bad Request error. " + \
        "Status code: %s" % status_code
    step("### Port not modified. Status code is 400 Bad Request  ###\n")

    step("\n########## End Test create same Port ##########\n")


def verify_attribute_type(step):

    step("\n########## Test to verify attribute types ##########\n")

    step("\nAttempting to create port with incorrect type in attributes\n")

    data = [("ip4_address", 192, http.client.BAD_REQUEST),
            ("ip4_address", "192.168.0.1", http.client.CREATED),
            ("tag", "675", http.client.BAD_REQUEST),
            ("tag", 675, http.client.CREATED),
            ("trunks", "654, 675", http.client.BAD_REQUEST),
            ("trunks", [654, 675], http.client.CREATED)]
    results = execute_port_operations(data, "PortTypeTest", "POST",
                                      PATH, SWITCH_IP,
                                      cookie_header)

    assert results, "Unable to execute requests in verify_attribute_type"

    for attribute in results:
        assert attribute[1], "%s code issued " % attribute[2] + \
            "instead of %s for type " % attribute[3] + \
            "test in field '%s'" % attribute[0]
        step("%s code received as expected for field %s!\n" %
             (attribute[2], attribute[0]))

    step("\n########## End test to verify attribute types ##########\n")


def verify_attribute_range(step):

    step("\n########## Test to verify attribute ranges ##########\n")

    step("\nAttempting to create a port with out of range values in "
         "attributes\n")

    interfaces_out_of_range = []
    for i in range(1, 10):
        interfaces_out_of_range.append("/rest/v1/system/interfaces/%s" % i)

    data = [("ip4_address", "175.167.134.123/248", http.client.BAD_REQUEST),
            ("ip4_address", "175.167.134.123/24", http.client.CREATED),
            ("tag", 4095, http.client.BAD_REQUEST),
            ("tag", 675, http.client.CREATED),
            ("interfaces", interfaces_out_of_range, http.client.BAD_REQUEST),
            ("interfaces", ["/rest/v1/system/interfaces/1"],
             http.client.CREATED)]
    results = execute_port_operations(data, "PortRangesTest", "POST",
                                      PATH, SWITCH_IP,
                                      cookie_header)

    assert results, "Unable to execute requests in verify_attribute_range"

    for attribute in results:
        assert attribute[1], "%s code issued " % attribute[2] + \
            "instead of %s for value range " % attribute[3] + \
            "test in field '%s'" % attribute[0]
        step("%s code received as expected for field %s!\n" %
             (attribute[2], attribute[0]))

    step("\n########## End test to verify attribute ranges ##########\n")


def verify_attribute_value(step):

    step("\n########## Test to verify attribute valid value ##########\n")

    step("\nAttempting to create port with invalid value in attributes\n")

    data = [("vlan_mode", "invalid_value", http.client.BAD_REQUEST),
            ("vlan_mode", "access", http.client.CREATED)]

    results = execute_port_operations(data, "PortValidValueTest", "POST",
                                      PATH, SWITCH_IP,
                                      cookie_header)

    assert results, "Unable to execute requests in verify_attribute_value"

    for attribute in results:
        assert attribute[1], "%s code issued " % attribute[2] + \
            "instead of %s for attribute " % attribute[3] + \
            "valid value test in field '%s'" % attribute[0]
        step("%s code received as expected for field %s!\n" %
             (attribute[2], attribute[0]))

    step("\n########## End test to verify attribute valid value "
         "##########\n")


def verify_missing_attribute(step):

    step("\n########## Test to verify missing attribute ##########\n")

    request_data = deepcopy(PORT_DATA)

    # Try to POST a port with missing attribute in request data

    step("\nAttempting to create a port with missing attribute in request "
         "data\n")

    del request_data['configuration']['name']

    status_code, response_data = execute_request(
        PATH, "POST", json.dumps(request_data), SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "%s code issued instead of BAD_REQUEST for Port with missing " + \
        "attribute" % status_code

    step("BAD_REQUEST code received as expected!")

    # Try to POST a port with all attributes in request data

    step("\nAttempting to create port with all attributes in request " +
         "data\n")

    request_data['configuration']['name'] = 'PortAllAttributes'

    status_code, response_data = execute_request(
        PATH, "POST", json.dumps(request_data), SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.CREATED, \
        "Got %s code instead of CREATED for Port with all attributes" % \
        status_code

    step("CREATE code received as expected!\n")

    step("\n########## End test to verify missing attribute ##########\n")


def verify_unknown_attribute(step):

    step("\n########## Test to verify unkown attribute ##########\n")

    step("\nAttempting to create a port with an unknown attribute\n")

    data = [("unknown_attribute", "unknown_value", http.client.BAD_REQUEST),
            ("vlan_mode", "access", http.client.CREATED)]

    results = execute_port_operations(data, "PortUnknownAttributeTest",
                                      "POST", PATH, SWITCH_IP,
                                      cookie_header)

    assert results, "Unable to execute request in verify_unknown_attribute"

    for attribute in results:
        assert attribute[1], "%s code issued " % attribute[2] + \
            "instead of %s for unknown " % attribute[3] + \
            "attribute test in field '%s'" % attribute[0]
        step("%s code received as expected for field %s!\n" %
             (attribute[2], attribute[0]))

    step("\n########## End test to verify unkown attribute ##########\n")


def verify_malformed_json(step):

    step("\n########## Test to verify malformed JSON ##########\n")

    request_data = deepcopy(PORT_DATA)

    # Try to POST a port with a malformed JSON in request data

    step("\nAttempting to create port with a malformed JSON in request " +
         "data\n")

    request_data['configuration']['name'] = 'PortMalformedJSON'
    json_string = json.dumps(request_data)
    json_string += ","

    status_code, response_data = execute_request(
        PATH, "POST", json_string, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "%s code issued instead of BAD_REQUEST for Port with " + \
        "malformed JSON in request data" % status_code

    # Try to POST a port with a correct JSON in request data

    step("\nAttempting to create port with a correct JSON in request"
         "data\n")

    request_data['configuration']['name'] = 'PortCorrectJSON'
    json_string = json.dumps(request_data)

    status_code, response_data = execute_request(
        PATH, "POST", json_string, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.CREATED, \
        "%s code issued instead of CREATED for Port with correct JSON " + \
        "in request data" % status_code

    step("\n########## End test to verify malformed JSON ##########\n")


def test_ops_restd_ft_ports_post(topology, step, netop_login, sanity_check):
    global switches
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    create_port_with_depth(step)
    create_port(step)
    create_same_port(step)
    verify_attribute_type(step)
    verify_attribute_range(step)
    verify_attribute_value(step)
    verify_missing_attribute(step)
    verify_unknown_attribute(step)
    verify_malformed_json(step)
    step("container_id_test %s\n" % switches[0].container_id)
    swagger_model_verification(switches[0].container_id, "/system/ports",
                               "POST", PORT_DATA)
