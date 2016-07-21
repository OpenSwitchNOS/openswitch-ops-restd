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

from rest_utils_ft import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    create_test_ports, get_server_crt, remove_server_crt
)

import http.client

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
NUM_PORTS = 100

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
    status_code = create_test_ports(SWITCH_IP, NUM_PORTS)
    assert status_code == http.client.CREATED, "Failed to create test ports"


def pagination_empty_offset(step, path):
    step("### Attempting to fetch first 5 ports in the list with" +
         " no offset set ###\n")

    status_code, response_data = execute_request(
        path + ";limit=5", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    assert json_data_len == 5, "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)

    assert json_data[0]["configuration"]["name"] == "bridge_normal", \
        "Wrong initial port: %s" % json_data[0]["configuration"]["name"]
    step("### Correct offset was set by default ###\n")


def pagination_empty_limit(step, path):
    step("### Attempting to fetch last 10 ports in the list with" +
         " no limit set ###\n")

    status_code, response_data = execute_request(
        path + ";offset=91", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    assert json_data_len == 10, "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)

    assert json_data[0]["configuration"]["name"] == "Port90", \
        "Wrong initial port: %s" % json_data[0]["configuration"]["name"]
    assert json_data[9]["configuration"]["name"] == "Port99", \
        "Wrong final port: %s" % json_data[9]["configuration"]["name"]
    step("### Correct limit was set by default ###\n")


def pagination_no_offset_limit(step, path):
    step("### Attempting to fetch ports with no offset or limit set ###\n")

    status_code, response_data = execute_request(
        path, "GET", None, SWITCH_IP, xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    # There a total fo NUM_PORTS + 1 (counting the default port)
    assert json_data_len == NUM_PORTS + 1, \
        "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)


def pagination_negative_offset(step, path):
    step("### Attempting to fetch ports with negative offset ###\n")

    status_code, response_data = execute_request(
        path + ";offset=-1;limit=10", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_negative_limit(step, path):
    step("### Attempting to fetch ports with negative limit ###\n")

    status_code, response_data = execute_request(
        path + ";offset=5;limit=-1", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_offset_greater_than_data(step, path):
    step("### Attempting to fetch ports with offset larger than" +
         " data size ###\n")

    status_code, response_data = execute_request(
        path + ";offset=200", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_offset_remainder(step, path):
    step("### Attempting to fetch remainder 10 ports in the list using " +
         "large limit ###\n")

    status_code, response_data = execute_request(
        path + ";offset=91;limit=20", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    assert json_data_len == 10, "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)

    assert json_data[0]["configuration"]["name"] == "Port90", \
        "Wrong initial port: %s" % json_data[0]["configuration"]["name"]
    assert json_data[9]["configuration"]["name"] == "Port99", \
        "Wrong final port: %s" % json_data[9]["configuration"]["name"]
    step("### Expected remainder ports are returned " +
         "using large limit ###\n")


def pagination_offset_limit_non_plural(step):
    step("### Attempting to fetch single port with offset and limit " +
         "present ###\n")

    status_code, response_data = execute_request(
        PATH + "/bridge_normal?depth=1" + ";offset=0;limit=10",
        "GET", None, SWITCH_IP, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_offset_only_non_plural(step):
    step("### Attempting to fetch single port with offset " +
         "present ###\n")

    status_code, response_data = execute_request(
        PATH + "/bridge_normal?depth=1" + ";offset=5",
        "GET", None, SWITCH_IP, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_limit_only_non_plural(step):
    step("### Attempting to fetch single port with offset " +
         "present ###\n")

    status_code, response_data = execute_request(
        PATH + "/bridge_normal?depth=1" + ";limit=5",
        "GET", None, SWITCH_IP, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, \
        "Wrong status code %s " % status_code
    step("### Status code is BAD_REQUEST ###\n")


def pagination_indexes(step):
    step("\n########## Test to validate pagination indexes of GET" +
         " request results ##########\n")

    path = PATH + "?depth=1;sort=name"

    # Test empty offset, it should default to 0
    pagination_empty_offset(step, path)

    # Test empty limit with offset set to 91,
    # it should return the last 10 ports
    pagination_empty_limit(step, path)

    # Test GET with no offset or limit set,
    # the entire port list should be returned
    pagination_no_offset_limit(step, path)

    # Test negative offset
    pagination_negative_offset(step, path)

    # Test negative limit
    pagination_negative_limit(step, path)

    # Test an offset greater than total data size
    pagination_offset_greater_than_data(step, path)

    # Test (offset + limit) > total ports
    # Ports from offset to the end should be returned
    pagination_offset_remainder(step, path)

    # Test offset and limit present for non-plural resource
    pagination_offset_limit_non_plural(step)

    # Test offset present for non-plural resource
    pagination_offset_only_non_plural(step)

    # Test limit present for non-plural resource
    pagination_limit_only_non_plural(step)

    step("\n########## End test to validate pagination indexes of GET" +
         " request results ##########\n")


def query_ports_paginated(step):
    step("\n########## Test to Validate pagination of GET request" +
         " results ##########\n")

    # Request will be of depth = 1, with ports sorted by name
    path = PATH + "?depth=1;sort=name"

    # Request first 10 Ports

    step("### Attempting to fetch first 10 ports in the list ###\n")

    status_code, response_data = execute_request(
        path + ";offset=0;limit=10", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    assert json_data_len == 10, "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)

    # Ports are sorted alphabetically by name
    # Test ports are named Port0-Port100, when
    # sorted alphabetically: Port0, Port1, Port11, Port12...

    assert json_data[0]["configuration"]["name"] == "bridge_normal", \
        "Wrong initial port: %s" % json_data[0]["configuration"]["name"]
    assert json_data[9]["configuration"]["name"] == "Port16", \
        "Wrong final port: %s" % json_data[9]["configuration"]["name"]
    step("### Correct set of ports returned ###\n")

    # Request 10 ports from the list end

    step("### Attempting to fetch last 10 ports in the list ###\n")

    status_code, response_data = execute_request(
        path + ";offset=91;limit=10", "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    json_data_len = len(json_data)

    assert json_data_len == 10, "Wrong request size %s " % json_data_len
    step("### Correct number of ports returned: %s  ###\n" % json_data_len)

    assert json_data[0]["configuration"]["name"] == "Port90", \
        "Wrong initial port: %s" % json_data[0]["configuration"]["name"]
    assert json_data[9]["configuration"]["name"] == "Port99", \
        "Wrong final port: %s" % json_data[9]["configuration"]["name"]
    step("### Correct set of ports returned ###\n")

    step("\n########## End Test to Validate pagination of GET request" +
         " results ##########\n")


@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_ports_get_pagination(topology, step, netop_login,
                                           setup_test):
    sw1 = topology.get("ops1")
    assert sw1 is not None

    global dir
    dir = "/ws/manesay/rest_0701/genericx86-64/src/"
    global daemon_name
    daemon_name = "restd"
    global dir_name
    dir_name = "ops-restd"
    global src_dir_name
    src_dir_name = "ops-restd/opsrest,ops-restd/opsplugins,ops-restd/opsvalidator,ops-restd/opslib"
    global file_name
    file_name = dir_name + "/restd.py"

    sw1("systemctl stop " + daemon_name, shell="bash")
    sw1("cd " + dir, shell="bash")
    sw1("coverage run -a --source=" + src_dir_name + " " + file_name +  " &", shell="bash")
    sleep(10)

    pagination_indexes(step)
    query_ports_paginated(step)

    sw1("cd " + dir, shell="bash")
    sw1("ps -ef | grep " + daemon_name + " | grep -v grep | awk '{print $2}' | xargs kill -2", shell="bash")
    sw1("cp .coverage " + dir_name + "/coverage_report/.coverage", shell="bash")
    sw1("systemctl start " + daemon_name, shell="bash")
    sleep(10)
