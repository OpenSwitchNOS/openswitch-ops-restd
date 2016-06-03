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

from pytest import fixture, mark


import json
import http.client

from rest_utils import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    get_server_crt, remove_server_crt, create_test_port
)

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


def delete_port_with_depth(step):
    step("\n########## Test delete Port with depth ##########\n")
    status_code, response_data = execute_request(
        PORT_PATH + "?depth=1", "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert status_code == http.client.BAD_REQUEST, \
        "Is not sending No Content status code. Status code: %s" % status_code
    step("### Status code is 400 BAD REQUEST  ###\n")

    step("\n########## End Test delete Port with depth ##########\n")


def delete_port(step):
    step("\n########## Test delete Port ##########\n")
    status_code, response_data = execute_request(
        PORT_PATH, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert status_code == http.client.NO_CONTENT, \
        "Is not sending No Content status code. Status code: %s" % status_code
    step("### Status code is 204 No Content  ###\n")

    step("\n########## End Test delete Port ##########\n")


def verify_deleted_port_from_port_list(step):
    step("\n########## Test Verify if Port is deleted from port list "
         "##########\n")
    # Verify if port has been deleted from the list
    status_code, response_data = execute_request(
        PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    json_data = []
    try:
        json_data = json.loads(response_data.decode("utf-8"))
    except:
        assert False, "Malformed JSON"

    assert \
        PORT_PATH not in json_data, "Port has not been deleted from port list"
    step("### Port not in list  ###\n")

    step("\n########## End Test Verify if Port is deleted from port list"
         "##########\n")


def verify_deleted_port(step):
    step("\n########## Test Verify if Port is found ##########\n")
    # Verify deleted port
    status_code, response_data = execute_request(
        PORT_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header
    )

    assert status_code == http.client.NOT_FOUND, "Port has not be deleted"
    step("### Port not found  ###\n")

    step("\n########## End Test Verify if Port is found ##########\n")


def delete_non_existent_port(step):
    step("\n########## Test delete non-existent Port ##########\n")
    new_path = PATH + "/Port2"
    status_code, response_data = execute_request(
        new_path, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert \
        status_code == http.client.NOT_FOUND, "Validation failed, is not" \
        " sending Not Found error. Status code: %s" % status_code
    step("### Status code is 404 Not Found  ###\n")

    step("\n########## End Test delete non-existent Port  ##########\n")


@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_ports_delete(topology, step, netop_login, setup_test):
    delete_port_with_depth(step)
    delete_port(step)
    verify_deleted_port_from_port_list(step)
    verify_deleted_port(step)
    delete_non_existent_port(step)
