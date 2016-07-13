# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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
import http.client
from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, get_server_crt, \
    remove_server_crt, get_json
from time import sleep

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

DEPTH_MAX_VALUE = 10
SWITCH_IP = None
sw1 = None
PATH = "/rest/v1/system/interfaces"
cookie_header = None


@fixture(scope="module")
def setup_module(request, topology):
    sleep(2)
    get_server_crt(sw1)
    rest_sanity_check(SWITCH_IP)

    def cleanup():
        remove_server_crt()

    request.addfinalizer(cleanup)


@fixture()
def setup(request, topology):
    global sw1
    if sw1 is None:
        sw1 = topology.get("sw1")
    assert sw1 is not None
    global SWITCH_IP
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(sw1)
    global cookie_header
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        cookie_header = None

    request.addfinalizer(cleanup)


def validate_keys_complete_object(json_data):
    assert json_data["configuration"] is not None

    return True


def validate_keys_inner_object(json_data, json_expected_data):
    assert json_data["split_parent"] is not None
    print("### split_parent, split_children keys present ###\n")
    assert json_data == json_expected_data
    print("### Configuration data validated ###\n")

    assert json_data["split_parent"][0] == \
        json_expected_data["split_parent"][0]
    print("### URI present in second level received ###\n")

    return True


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_depth_first_level(setup, setup_module, topology, step):
    specific_interface_path = PATH + "/50-1"
    depth_interface_path = PATH + "?depth=1;name=50-1"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)
    json_data = get_json(response_data)[0]

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=1 request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_expected_data = json_expected_data["configuration"]
    json_data = json_data["configuration"]

    assert validate_keys_inner_object(json_data, json_expected_data)
    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=1 request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_depth_second_level(setup, setup_module, topology, step):
    specific_interface_path = PATH + "/50"
    depth_interface_path = PATH + "?depth=2;name=50-1"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)
    json_data = get_json(response_data)[0]

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=2 request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_data = json_data["configuration"]["split_parent"][0]

    assert validate_keys_complete_object(json_data)
    step("### Validated second level of depth###\n")

    assert len(set(json_data["configuration"]) &
               set(json_expected_data["configuration"])) > 0
    assert json_data["configuration"]["split_children"].sort() == \
        json_expected_data["configuration"]["split_children"].sort()
    step("### Data for the third level received ###\n")

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=2 request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_with_depth_max_value(setup, setup_module, topology,
                                            step):
    specific_interface_path = PATH + "/50-1?selector=configuration;depth=%d" \
                                      % DEPTH_MAX_VALUE
    depth_interface_path = PATH + "?selector=configuration;depth=%d;name=50-1"\
                                  % DEPTH_MAX_VALUE
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)
    json_data = get_json(response_data)[0]

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=10 request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_expected_data = json_expected_data["configuration"]
    json_data = json_data["configuration"]

    assert validate_keys_inner_object(json_data, json_expected_data)
    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=10 request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_validate_negative_depth_value(setup, setup_module,
                                                     topology, step):
    depth_interface_path = PATH + "?depth=-1"
    status_code, response_data = execute_request(depth_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=<negative value> request ##########\n")

    assert status_code == http.client.BAD_REQUEST
    step("### Status code is BAD_REQUEST for URI: %s ###\n" %
         depth_interface_path)

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=<negative value> request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_validate_depth_higher_max_value(setup, setup_module,
                                                       topology, step):
    test_title = "Test to Validate recursive GET Interfaces with " \
                 "depth > DEPTH_MAX_VALUE"
    depth_values = [100, 1000]
    step("\n########## " + test_title + " ##########\n")
    for i in range(0, len(depth_values)):
        depth_interface_path = PATH + "?depth=%d" % depth_values[i]
        status_code, response_data = execute_request(depth_interface_path,
                                                     "GET", None, SWITCH_IP,
                                                     xtra_header=cookie_header)
        assert status_code == http.client.BAD_REQUEST
        step("### Status code is BAD_REQUEST for URI: %s ###\n" %
             depth_interface_path)
        step("Response Message: %s\n" % response_data)
    step("########## End " + test_title + " ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_validate_string_depth_value(setup, setup_module,
                                                   topology, step):
    test_title = "Test to Validate recursive GET Interfaces with " \
                 "depth=<string>"
    depth_values = ["a", "one", "*"]
    step("\n########## " + test_title + " ##########\n")
    for i in range(0, len(depth_values)):
        depth_interface_path = PATH + "?depth=%s" % depth_values[i]
        status_code, response_data = execute_request(depth_interface_path,
                                                     "GET", None, SWITCH_IP,
                                                     xtra_header=cookie_header)
        assert status_code == http.client.BAD_REQUEST
        step("### Status code is BAD_REQUEST for URI: %s ###\n" %
             depth_interface_path)
        step("Response Message: %s\n" % response_data)
    step("########## End " + test_title + " ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_validate_with_depth_zero(setup, setup_module,
                                                topology, step):
    expected_data = PATH + "/50"
    depth_interface_path = PATH + "?depth=0"
    status_code, response_data = execute_request(depth_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_data = get_json(response_data)

    step("\n########## Test to Validate recursive GET interfaces "
         "with depth=0 request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None

    assert len(json_data) > 0
    assert expected_data in json_data
    step("### There is at least one interface  ###\n")

    step("########## End Test to Validate recursive GET interfaces "
         "with depth=0 request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_all_interfaces_no_depth_parameter(setup, setup_module,
                                                         topology, step):
    expected_data = PATH + "/50"
    status_code, response_data = execute_request(PATH, "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_data = get_json(response_data)

    step("\n########## Test to Validate first GET all Interfaces "
         "no depth parameter request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None

    assert len(json_data) > 0
    assert expected_data in json_data
    step("### There is at least one interface  ###\n")

    step("########## End Test to Validate first GET all Interfaces "
         "no depth parameter request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_depth_first_level_specific_uri(setup, setup_module,
                                                      topology, step):
    specific_interface_path = PATH + "?depth=1;name=50-1"
    depth_interface_path = PATH + "/50-1?depth=1"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)[0]
    json_data = get_json(response_data)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=1 specific uri request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_expected_data = json_expected_data["configuration"]
    json_data = json_data["configuration"]

    assert validate_keys_inner_object(json_data, json_expected_data)
    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=1 specific uri request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_depth_second_level_specific_uri(setup, setup_module,
                                                       topology, step):
    specific_interface_path = PATH + "?selector=configuration;depth=2;name=50-1"  # noqa
    depth_interface_path = PATH + "/50-1?selector=configuration;depth=2"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)[0]
    json_data = get_json(response_data)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=2 specific uri request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth###\n")

    json_data = json_data["configuration"]["split_parent"][0]
    json_expected_data = json_expected_data["configuration"]["split_parent"][0]

    assert validate_keys_complete_object(json_data)
    step("### Validated second level of depth###\n")

    assert len(set(json_data["configuration"]) &
               set(json_expected_data["configuration"])) > 0
    assert json_data == json_expected_data
    step("### Data for the third level received ###\n")

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=2 specific uri request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_with_negative_depth_value_specific_uri(setup,
                                                              setup_module,
                                                              topology, step):
    depth_interface_path = PATH + "/50-1?depth=-1"
    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=<negative value> specific uri request\n")

    assert status_code == http.client.BAD_REQUEST
    step("### Status code is BAD_REQUEST for URI: %s ###\n" %
         depth_interface_path)

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=<negative value> specific uri request\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_with_string_depth_value_specific_uri(setup,
                                                            setup_module,
                                                            topology, step):
    depth_interface_path = PATH + "/50-1?depth=a"
    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "depth=<string> specific uri request\n")

    assert status_code == http.client.BAD_REQUEST
    step("### Status code is BAD_REQUEST for URI: %s ###\n" %
         depth_interface_path)

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "depth=<string> specific uri request\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_specific_uri_with_depth_zero(setup, setup_module,
                                                    topology, step):
    specific_interface_path = PATH + "?selector=configuration;depth=1;name=50-1"  # noqa
    depth_interface_path = PATH + "/50-1?selector=configuration;depth=0"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)
    json_expected_data = get_json(expected_data)[0]
    json_data = get_json(response_data)

    step("\n########## Test to Validate GET specific Interface with "
         "depth=0 request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_data = json_data["configuration"]
    json_expected_data = json_expected_data["configuration"]

    assert validate_keys_inner_object(json_data, json_expected_data)
    step("########## End Test to Validate GET specific Interface with "
         "depth=0 request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_specific_uri_no_depth_parameter(setup, setup_module,
                                                       topology, step):
    specific_interface_path = PATH + "?depth=1;name=50-1"
    depth_interface_path = PATH + "/50-1"
    status_code, expected_data = execute_request(specific_interface_path,
                                                 "GET", None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    status_code, response_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    json_expected_data = get_json(expected_data)[0]
    json_data = get_json(response_data)

    step("\n########## Test to Validate GET specific Interface with "
         "no depth request ##########\n")

    assert status_code == http.client.OK
    step("### Status code is OK ###\n")

    assert response_data is not None

    assert validate_keys_complete_object(json_data)
    step("### Validated first level of depth ###\n")

    json_data = json_data["configuration"]
    json_expected_data = json_expected_data["configuration"]

    assert validate_keys_inner_object(json_data, json_expected_data)
    step("########## End Test to Validate GET specific Interface with "
         "no depth request ##########\n")


@mark.skipif(True, reason="Disabling because test is failing")
def test_recursive_get_depth_out_range(setup, setup_module, topology, step):
    depth_interface_path = PATH + "?depth=11;name=50-1"
    status_code, expected_data = execute_request(depth_interface_path, "GET",
                                                 None, SWITCH_IP,
                                                 xtra_header=cookie_header)

    step("\n########## Test to Validate recursive GET Interface 50-1 "
         "out of range request ##########\n")

    assert status_code == http.client.BAD_REQUEST
    step("### Status code is BAD REQUEST ###\n")

    step("########## End Test to Validate recursive GET Interface 50-1 "
         "out of range request ##########\n")
