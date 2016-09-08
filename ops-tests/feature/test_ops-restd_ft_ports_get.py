# -*- coding: utf-8 -*-

# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHoutput ANY WARRANTY; withoutput even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.


import http.client

from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, create_test_port, \
    get_container_id, PORT_DATA, get_server_crt, \
    remove_server_crt, get_json

from swagger_test_utility import swagger_model_verification
from pytest import mark

# Topology definition. the topology contains two back to back switches
# having four links between them.

TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
"""

SWITCH_IP = None
switch = None
# get_switch_ip(net.switches[0])
PATH = "/rest/v1/system/ports"
PORT_PATH = PATH + "/Port1"
cookie_header = None
container_id = None


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def query_all_ports(step):
    step("\n########## Test to Validate first GET all Ports request \
          ##########\n")

    status_code, response_data = execute_request(
        PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned: %s ###\n" % response_data)

    json_data = {}
    try:
        json_data = get_json(response_data)
    except:
        assert False, "Malformed JSON"

    assert len(json_data) > 0, "Wrong ports size %s " % len(json_data)
    step("### There is at least one port  ###\n")

    assert PORT_PATH in json_data, "Port is not in data. \
                                         Data returned is: %s" \
                                         % response_data[0]
    step("### Port is in list  ###\n")

    step("\n########## End Test to Validate first GET all Ports request \
        ##########\n")


def query_port(step):
    step("\n########## Test to Validate first GET single Port request \
        ##########\n")

    status_code, response_data = execute_request(
        PORT_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned: %s ###\n" % response_data)

    json_data = {}
    try:
        json_data = get_json(response_data)
    except:
        assert False, "Malformed JSON"

    assert json_data["configuration"] is not None, \
        "configuration key is not present"
    assert json_data["statistics"] is not None, \
        "statistics key is not present"
    assert json_data["status"] is not None, "status key is not present"
    step("### Configuration, statistics and status keys present ###\n")

    assert json_data["configuration"] == PORT_DATA["configuration"], \
        "Configuration data is not equal that posted data"
    step("### Configuration data validated ###\n")

    step("\n########## End Test to Validate first GET single Port request \
        ##########\n")


def query_non_existent_port(step):
    step("\n########## Test to Validate first GET Non-existent Port \
         request  ##########\n")

    new_path = PATH + "/Port2"
    status_code, response_data = execute_request(
        new_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.NOT_FOUND, "Wrong status code %s " \
        % status_code
    step("### Status code is NOT FOUND ###\n")

    step("\n########## End Test to Validate first GET Non-existent Port \
        request ##########\n")


def _setup(step):
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)
    # Add a test port
    step("\n########## Creating Test Port  ##########\n")
    status_code, response = create_test_port(SWITCH_IP)
    assert status_code == http.client.CREATED, "Port not created."\
        "Response %s" % response
    step("### Test Port Created  ###\n")
    global container_id
    container_id = get_container_id(switch)


def _teardown():
    remove_server_crt()


@mark.gate
def test_ops_restd_ft_ports_get(topology, step):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup(step)
    _netop_login()
    query_all_ports(step)
    query_port(step)
    query_non_existent_port(step)
    step("container_id_test %s\n" % container_id)
    swagger_model_verification(container_id, "/system/ports/{id}",
                               "GET_ID", PORT_DATA, SWITCH_IP)
    _teardown()
