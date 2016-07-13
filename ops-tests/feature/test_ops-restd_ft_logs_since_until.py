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

from pytest import fixture, mark
from os import environ
import http.client
import time
import datetime

from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, get_json, get_server_crt, \
    remove_server_crt

TOPOLOGY = """
#               +-------+
# +-------+     |       |
# |  sw1  <----->  hsw1 |
# +-------+     |       |
#               +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=oobmhost name="Host 1"] h1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- h1:if01
"""

OFFSET_TEST = 0
LIMIT_TEST = 1000
PATH = "/rest/v1/logs"
cookie_header = None
SWITCH_IP = None
sw1 = None


@fixture(scope="module")
def setup_module(topology):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    time.sleep(2)
    get_server_crt(sw1)
    rest_sanity_check(SWITCH_IP)


@fixture()
def setup(request, topology):
    global sw1
    sw1 = topology.get("sw1")
    assert sw1 is not None
    global SWITCH_IP
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(sw1)
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(sw1)
    global cookie_header
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        remove_server_crt()
        cookie_header = None

    request.addfinalizer(cleanup)


def verify_timestamp(json_data):
    for t in json_data:
        if float(t["__REALTIME_TIMESTAMP"]) < (time.time() - 60):
            return False
    return True


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_logs_with_since_relative_filter(setup, setup_module, topology, step):
    step("\n########## Test to Validate logs with since relative filter" +
         " ##########\n")

    # bug_flag = True
    since_test = "1%20minute%20ago"

    logs_path = PATH + "?since=%s&offset=%s&limit=%s" % \
        (since_test, OFFSET_TEST, LIMIT_TEST)

    step("logs path %s" % logs_path)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None
    step("### Response data returned for logs with since filter  ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST
    step("### Pagination for logs works fine ###\n")

    assert verify_timestamp(json_data)
    step("### Since filter for logs is working fine ###\n")

    step("\n########## End Test to Validate logs with since relative" +
         " filter ##########\n")


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_logs_with_since_timestamp_filter(setup, setup_module, topology, step):
    step("\n########## Test to Validate logs with since timestamp" +
         "##########\n")

    since_test = str(datetime.datetime.now()).split('.')[0]
    since_test = since_test.replace(" ", "%20")

    logs_path = PATH + "?since=%s&offset=%s&limit=%s" % \
        (since_test, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None
    step("### Response data returned for logs with since timestamp" +
         "filter ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST
    step("### Pagination for logs works fine ###\n")

    assert verify_timestamp(json_data)
    step("### Since filter for logs is working fine ###\n")

    step("\n########## End Test to Validate logs with since timestamp" +
         "##########\n")


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_logs_with_since_negative_test_cases(setup, setup_module, topology,
                                             step):
    step("\n########## Test to Validate negative test cases for logs" +
         " with since timestamp ##########\n")

    since_test = "0000-00-00%2000:00:00"
    logs_path = PATH + "?since=%s&offset=%s&limit=%s" \
        % (since_test, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST
    step("### Status code for since 0000-00-00 00:00:00 "
         "case is okay ###\n")

    since_test = "2050-01-01%2001:00:00"
    logs_path = PATH + "?since=%s&offset=%s&limit=%s" \
        % (since_test, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code for since 2050-01-01 01:00:00 case is OK ###\n")

    assert "Empty logs" in str(response_data)
    step("### Response data returned for empty logs returned fine  ###\n")

    since_test = "-1%20hour%20ago"
    logs_path = PATH + "?since=%s&offset=%s&limit=%s" \
        % (since_test, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST
    step("### Status code for since parameter with negative "
         "value is okay ###\n")

    step("\n########## End Test to Validate negative test case for logs" +
         " with since timestamp ##########\n")


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_logs_with_until_relative_filter(setup, setup_module, topology, step):
    step("\n########## Test to Validate logs with until relative filter" +
         "##########\n")

    # bug_flag = True

    logs_path = PATH + "?until=now"

    step("logs path %s\n" % logs_path)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None
    step("### Response data returned for logs with until filter  ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST
    step("### Pagination for logs works fine ###\n")

    assert verify_timestamp(json_data)
    step("### Until filter for logs is working fine ###\n")

    step("\n########## End Test to Validate logs with until relative" +
         " filter ##########\n")


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_logs_with_until_timestamp_filter(setup, setup_module, topology, step):
    step("\n########## Test to Validate logs with until timestamp" +
         "##########\n")

    until_test = str(datetime.datetime.utcnow()).split('.')[0]
    until_test = until_test.replace(" ", "%20")

    logs_path = PATH + "?until=%s&offset=%s&limit=%s" % \
        (until_test, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(logs_path, "GET", None,
                                                 SWITCH_IP,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None
    step("### Response data returned for logs with until timestamp" +
         "filter ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST
    step("### Pagination for logs works fine ###\n")

    assert verify_timestamp(json_data)
    step("### Until filter for logs is working fine ###\n")

    step("\n########## End Test to Validate logs with until timestamp" +
         "##########\n")
