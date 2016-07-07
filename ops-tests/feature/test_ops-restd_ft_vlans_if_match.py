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

from rest_utils_ft import (
    execute_request, login, rest_sanity_check, get_switch_ip, compare_dict,
    get_server_crt, remove_server_crt
)
from fakes import create_fake_vlan, FAKE_VLAN_DATA
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

TEST_HEADER = "Test to validate If-Match"
TEST_START = "\n########## " + TEST_HEADER + " %s ##########\n"
TEST_END = "\n########## End " + TEST_HEADER + " %s ##########\n"

switches = []
vlan_id = None
vlan_name = None
vlan_path = None
vlan = None
config_selector = None


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
    global PATH, vlan_id, vlan_name, vlan_path, vlan, config_selector
    PATH = "/rest/v1/system/bridges"
    vlan_id = 1
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (PATH, DEFAULT_BRIDGE)
    vlan = "%s/%s/vlans/%s" % (PATH,
                               DEFAULT_BRIDGE,
                               vlan_name)
    config_selector = "?selector=configuration"
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


def test_put_vlan_with_star_etag(step, netop_login, setup_test):
    step(TEST_START % "PUT VLAN with star Etag")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # 2 - Modify data
    put_data = pre_put_get_data["configuration"]
    put_data["description"] = "Star Etag"

    # Add If-Match: '"*"' to the request
    config_data = {'configuration': put_data}
    headers = {"If-Match": '"*"'}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "PUT", json.dumps(config_data), SWITCH_IP,
        xtra_header=headers)

    assert status_code == http.client.OK, "Error modifying a VLAN using "\
        "if-match option. Status code: %s Response data: %s "\
        % (status_code, response_data)
    step("### VLAN Modified. Status code 200 OK  ###\n")

    # 3 - Verify Modified data
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "VLAN %s doesn't exists" % cond_path
    post_put_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        post_put_get_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    post_put_data = post_put_get_data["configuration"]

    assert compare_dict(post_put_data, put_data), "Configuration data is "\
        "not equal that posted data"
    step("### Configuration data validated %s ###\n" % response_data)

    step(TEST_END % "PUT VLAN with star Etag")


def test_put_vlan_etag_match(step, netop_login, setup_test):
    step(TEST_START % "PUT VLAN with matching Etag")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # 2 - Modify data
    put_data = pre_put_get_data["configuration"]
    put_data["description"] = "Etag match"

    config_data = {'configuration': put_data}
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "PUT", json.dumps(config_data), SWITCH_IP,
        False, headers)

    assert status_code == http.client.OK, "Error modifying "\
        "a VLAN using if-match(precondition failed) option. "\
        "Status code: %s Response data: %s " % (status_code, response_data)

    # 3 - Verify Modified data
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)
    assert status_code == http.client.OK, "VLAN %s doesn't exists" % cond_path

    post_put_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        post_put_get_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    post_put_data = post_put_get_data["configuration"]

    assert compare_dict(post_put_data, put_data), "Configuration data is "\
        "not equal that posted data"
    step("### Configuration data validated %s ###\n" % response_data)

    step(TEST_END % "PUT VLAN with matching Etag")


def test_put_vlan_same_state_not_matching_etag(step, netop_login,
                                               setup_test):
    step(TEST_START % "PUT VLAN with not matching Etag "
         "and not state change")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # 2 - Set not matching etag
    put_data = pre_put_get_data["configuration"]
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    # 2 - Set same unchanged data
    config_data = {'configuration': put_data}
    headers = {'If-Match': etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "PUT", json.dumps(config_data), SWITCH_IP,
        False, headers)

    assert status_code == http.client.OK, "Error modifying a VLAN using "\
        "if-match option. Status code: %s Response data: %s "\
        % (status_code, response_data)
    step("### VLAN Modified. Status code 200 OK  ###\n")

    # 3 - Verify Modified data
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "VLAN %s doesn't exists" % cond_path
    post_put_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        post_put_get_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    post_put_data = post_put_get_data["configuration"]

    assert compare_dict(post_put_data, put_data), "Configuration data "\
        "is not equal that posted data"
    step("### Configuration data validated %s ###\n" % response_data)

    step(TEST_END % "PUT VLAN with not matching Etag and not state change")


def test_put_vlan_etag_not_match(step, netop_login, setup_test):
    step(TEST_START % "PUT VLAN with not matching Etag")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # 2 - Modify data
    put_data = pre_put_get_data["configuration"]
    put_data["description"] = "Etag not match"
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    config_data = {'configuration': put_data}
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "PUT", json.dumps(config_data), SWITCH_IP,
        False, headers)

    assert status_code == http.client.PRECONDITION_FAILED, "Error modifying "\
        "a VLAN using if-match(precondition failed) option. "\
        "Status code: %s Response data: %s " % (status_code, response_data)
    step("### VLAN no Modified. Status code 412 OK  ###\n")

    step(TEST_END % "PUT VLAN with not matching Etag")


def test_post_vlan_etag_match(step, netop_login, setup_test):
    step(TEST_START % "POST VLAN with matching Etag")
    # 1 - Query Resource
    cond_path = vlan_path + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # Fill Vlan data
    fake_vlan_name = "VLAN2"
    vlan_id = 2
    data = FAKE_VLAN_DATA % {"name": fake_vlan_name, "id": vlan_id}

    # Try to create the resource using a valid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "POST", data, SWITCH_IP, False, headers)

    assert status_code == http.client.CREATED, "Error creating a VLAN using "\
        "if-match option. Status code: %s Response data: %s "\
        % (status_code, response_data)
    step("### VLAN Created. Status code 201 CREATED  ###\n")

    # Delete created VLAN
    delete_fake_vlan_if_exists(fake_vlan_name)

    step(TEST_END % "POST VLAN with matching Etag")


def test_post_vlan_etag_not_match(step, netop_login, setup_test):
    step(TEST_START % "POST VLAN with not matching Etag")
    # 1 - Query Resource
    cond_path = vlan_path + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)
    # Set wrong etag
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    # Fill Vlan data
    fake_vlan_name = "VLAN2"
    vlan_id = 2
    data = FAKE_VLAN_DATA % {"name": fake_vlan_name, "id": vlan_id}

    # Try to create the resource using a invalid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "POST", data, SWITCH_IP, False, headers)

    assert status_code == http.client.PRECONDITION_FAILED, "Error creating "\
        "using if-match using invalid etag. Status code: %s "\
        "Response data: %s " % (status_code, response_data)
    step("### VLAN No Created. Status code 412 Precondition Failed  ###\n")

    step(TEST_END % "POST VLAN with not matching Etag")


def test_get_all_vlan_etag_match(step, netop_login, setup_test):
    step(TEST_START % "GET all VLANs with matching Etag")
    # 1 - Query Resource
    cond_path = vlan_path + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # Try to retrieve the resource using a valid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, False, headers)
    assert status_code == http.client.OK, "Error retrieving VLANs using " \
        "valid etag Status code: %s Response data: %s " % \
        (status_code, response_data)
    step("### VLANs retrieved. Status code 200 OK  ###\n")

    step(TEST_END % "GET all VLANs with  matching Etag")


def test_get_all_vlan_etag_not_match(step, netop_login, setup_test):
    step(TEST_START % "GET all VLANs with not matching Etag")
    # 1 - Query Resource
    cond_path = vlan_path + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)
    # Set wrong etag
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    # Try to retrieve the resource using a invalid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, False, headers)

    assert status_code == http.client.PRECONDITION_FAILED,\
        "Error retrieving VLANs using invalid etag. Status code: %s" \
        "Response data: %s " % (status_code, response_data)
    step("### VLANs not retrieved. Status code 412 "
         "Precondition Failed  ###\n")

    step(TEST_END % "GET all VLANs with not matching Etag")


def test_get_vlan_etag_match(step, netop_login, setup_test):
    step(TEST_START % "GET VLAN with matching Etag")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # Try to retrieve the resource using a valid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, False, headers)

    assert status_code == http.client.OK, "Error retrieving VLAN using "\
        "valid etag Status code: %s Response data: %s " % \
        (status_code, response_data)
    step("### VLANs retrieved. Status code 200 OK  ###\n")

    step(TEST_END % "GET VLAN with matching Etag")


def test_get_vlan_etag_not_match(step, netop_login, setup_test):
    step(TEST_START % "GET VLAN with not matching Etag")
    # 1 - Query Resource
    cond_path = vlan + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)
    # Set wrong etag
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    # Try to retrieve the resource using a invalid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, False, headers)

    assert status_code == http.client.PRECONDITION_FAILED,\
        "Error retrieving VLAN using invalid etag. "\
        "Status code: %s Response data: %s " % (status_code, response_data)
    step("### VLANs not retrieved. Status code 412 "
         "Precondition Failed ###\n")

    step(TEST_END % "GET VLAN with not matching Etag")


def test_delete_vlan_etag_match(step, netop_login, setup_test):
    step(TEST_START % "DELETE VLAN with matching Etag")
    # 1- Create Fake VLAN
    fake_vlan_name = "VLAN2"
    vlan_id = 2
    create_fake_vlan(vlan_path,
                     SWITCH_IP,
                     fake_vlan_name, vlan_id)

    # 2- Query Resource
    cond_path = vlan_path + "/" + fake_vlan_name\
        + config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # 3- Delete the vlan using the matching etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "DELETE", None, SWITCH_IP, False, headers)

    assert status_code == http.client.NO_CONTENT, "Error deleting VLAN using "\
        "valid etag Status code: %s Response data: %s " % \
        (status_code, response_data)
    step("### VLAN deleted. Status code NOT CONTENT 204  ###\n")

    step(TEST_END % "DELETE VLAN with matching Etag")


def test_delete_vlan_etag_not_match(step, netop_login, setup_test):
    step(TEST_START % "DELETE VLAN with not matching Etag")
    # 1- Create Fake VLAN
    fake_vlan_name = "VLAN2"
    vlan_id = 2
    create_fake_vlan(vlan_path,
                     SWITCH_IP,
                     fake_vlan_name, vlan_id)

    # 2- Query Resource
    cond_path = vlan_path + "/" + fake_vlan_name +\
        config_selector
    etag, pre_put_get_data = get_etag_and_data(cond_path)

    # Set wrong etag
    if etag:
        etag = etag[::-1]
    else:
        etag = '"abcdef"'

    # 3- Try to delete the resource using a invalid etag
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, False, headers)

    assert status_code == http.client.PRECONDITION_FAILED, "Error deleting "\
        "VLAN using invalid etag. Status code: %s Response data: %s "\
        % (status_code, response_data)
    step("### VLANs not deleted. Status code 412 "
         "Precondition Failed ###\n")

    # Delete created VLAN
    delete_fake_vlan_if_exists(fake_vlan_name)

    step(TEST_END % "DELETE VLAN with not matching Etag")


def get_etag_and_data(cond_path):
    response, response_data = execute_request(
        cond_path, "GET", None, SWITCH_IP, True,
        xtra_header=cookie_header)

    status_code = response.status
    etag = response.getheader("Etag")
    assert status_code == http.client.OK, "VLAN %s doesn't exists" % cond_path
    print("Etag = %s" % etag)
    pre_put_get_data = {}
    try:
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        pre_put_get_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"
    print("\n### Query Resource %s  ###\n" % response_data)
    return etag, pre_put_get_data


@mark.platform_incompatible(['ostl'])
def delete_fake_vlan_if_exists(vlan_name):
    print("\n### Deleting VLAN %s  ###\n" % vlan_name)
    path = vlan_path + "/" + vlan_name
    status_code, response_data = execute_request(
        path, "GET", None, SWITCH_IP, xtra_header=cookie_header)

    if status_code == http.client.OK:
        status_code, response_data = execute_request(
            path, "DELETE", None, SWITCH_IP,
            xtra_header=cookie_header)

        assert status_code == http.client.NO_CONTENT, "VLAN deleted" % path
