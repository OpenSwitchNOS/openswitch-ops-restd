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

from pytest import fixture, mark
from copy import deepcopy
from json import dumps

from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, \
    get_server_crt, remove_server_crt

from swagger_test_utility import swagger_model_verification
from time import sleep
from os import environ
import http.client


# ############################################################################
#                                                                            #
#   Common Tests topology                                                    #
#                                                                            #
# ############################################################################
TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
"""


base_vlan_data = {
    "configuration": {
        "name": "test",
        "id": 1,
        "description": "test_vlan",
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

default_bridge = "bridge_normal"

switch_ip = None
switch = None
cookie_header = None
path = "/rest/v1/system/bridges"
vlan_path = "%s/%s/vlans" % (path, default_bridge)


@fixture(scope="module")
def sanity_check(topology):
    switch = topology.get("sw1")
    assert switch is not None
    sleep(2)
    get_server_crt(switch)
    rest_sanity_check(switch_ip)


@fixture()
def setup(request, topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global switch_ip
    if switch_ip is None:
        switch_ip = get_switch_ip(switch)
    global proxy
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switch)
    global cookie_header
    if cookie_header is None:
        cookie_header = login(switch_ip)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None

    request.addfinalizer(cleanup)


@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_basic_vlan(setup, sanity_check,
                                            topology, step):
    swagger_model_verification(switch.container_id,
                               "/system/bridges/{pid}/vlans",
                               "POST", base_vlan_data)

    data = """
           {
               "configuration": {
                   "name": "fake_vlan_1",
                   "id": 1,
                   "description": "test vlan",
                   "admin": ["up"],
                   "other_config": {},
                   "external_ids": {}
               }
           }
           """

    step("\n########## Executing POST to /system/bridges ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    response_status, response_data = execute_request(
        vlan_path, "POST", data, switch_ip,
        xtra_header=cookie_header)

    assert response_status == http.client.CREATED, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing POST to /system/bridges DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid name                     #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_name(setup, sanity_check,
                                              topology, step):
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

    step("\n########## Executing POST test with bad \"name\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"name\" as [%s] with value: %s\n" % (field,
                                                                  value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"name\" value "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid ID                       #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_id(setup, sanity_check,
                                            topology, step):
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
            vlan_path, "POST", dumps(value), switch_ip,
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


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid description              #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_description(setup, sanity_check,
                                                     topology, step):
    data = deepcopy(test_vlan_data)

    # Remove same type keys
    data.pop("string")
    data.pop("one_string")

    data["int"]["configuration"]["description"] = 1
    data["dict"]["configuration"]["description"] = {}
    data["empty_array"]["configuration"]["description"] = []
    data["multiple_string"]["configuration"]["description"] = \
        ["test_vlan_1", "test_vlan_3"]
    data["None"]["configuration"]["description"] = None
    data["boolean"]["configuration"]["description"] = True

    step("\n########## Executing POST test with bad \"description\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"description\" as [%s] with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"description\" value "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid admin                    #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_admin(setup, sanity_check,
                                               topology, step):
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

    step("\n########## Executing POST test with bad \"admin\" value "
         "##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"admin\" as %s with value: %s\n" % (field,
                                                                 value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"admin\" value "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid other_config             #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_other_config(setup, sanity_check,
                                                      topology, step):
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

    step("\n########## Executing POST test with bad \"other_config\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"other_config\" as [%s] with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"other_config\" value "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal using an invalid external_ids             #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_invalid_external_ids(setup, sanity_check,
                                                      topology, step):
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

    step("\n########## Executing POST test with bad \"external_ids\" "
         "value ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing field \"external_ids\" as %s with value: "
             "%s\n" % (field, value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with bad \"external_ids\" value "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN to bridge_normal with missing fields                       #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_missing_fields(setup, sanity_check,
                                                topology, step):
    data = {}
    data["name"] = deepcopy(base_vlan_data)
    data["id"] = deepcopy(base_vlan_data)

    data["name"]["configuration"].pop("name")
    data["id"]["configuration"].pop("id")

    step("\n########## Executing POST test with missing fields "
         "##########\n")
    step("Testing Path: %s\n" % vlan_path)

    for field, value in data.items():
        step("Testing missing field \"%s\" with value: %s\n" % (field,
                                                                value))

        response_status, response_data = execute_request(
            vlan_path, "POST", dumps(value), switch_ip,
            xtra_header=cookie_header)

        assert response_status == http.client.BAD_REQUEST, \
            "Response status received: %s\n" % response_status
        step("Response status received: \"%s\"\n" % response_status)

        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        step("Response data received: %s\n" % response_data)

    step("########## Executing POST test with missing fields DONE "
         "##########\n")


# ############################################################################
#                                                                            #
#   Create a VLAN that already exits to bridge_normal                        #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_post_duplicated(setup, sanity_check,
                                            topology, step):
    data = """
           {
               "configuration": {
                   "name": "fake_vlan_15",
                   "id": 15,
                   "description": "test vlan",
                   "admin": ["up"],
                   "other_config": {},
                   "external_ids": {}
               }
           }
           """

    step("\n########## Executing POST to /system/bridges ##########\n")
    step("Testing Path: %s\n" % vlan_path)

    response_status, response_data = execute_request(
        vlan_path, "POST", data, switch_ip,
        xtra_header=cookie_header)

    assert response_status == http.client.CREATED, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    # Create duplicated
    response_status, response_data = execute_request(
        vlan_path, "POST", data, switch_ip,
        xtra_header=cookie_header)

    assert response_status == http.client.BAD_REQUEST, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is not "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing POST to test duplicated VLAN DONE "
         "##########\n")
