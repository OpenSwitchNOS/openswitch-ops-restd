# -*- coding: utf-8 -*-

# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
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
from fakes import create_fake_vlan
from rest_utils_ft import execute_request, login, get_json, \
    get_switch_ip, rest_sanity_check, \
    compare_dict, get_server_crt, remove_server_crt
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

DEFAULT_BRIDGE = "bridge_normal"
switch_ip = None
cookie_header = None
switch = None


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
    if switch is None:
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
        output = switch("show run")
        if "vlan 2" in output:
            switch("conf t")
            switch("no vlan 2")
            switch("end")
        remove_server_crt()

    request.addfinalizer(cleanup)


# ############################################################################
#                                                                            #
#   Query for Bridge Normal                                                  #
#                                                                            #
# ############################################################################
@mark.gate
def test_ops_restd_ft_vlans_get_default_bridge_normal(setup, sanity_check,
                                                      topology, step):
    expected_data = ["/rest/v1/system/bridges/%s" % DEFAULT_BRIDGE]
    path = "/rest/v1/system/bridges"

    step("\n########## Executing GET to /system/bridges ##########\n")
    step("Testing Path: %s\n" % path)

    response_status, response_data = execute_request(
        path, "GET", None, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.OK, \
        "Response status received: %s\n" % response_status
    step("Response status received: %s\n" % response_status)

    assert get_json(response_data) == expected_data, \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing GET to /system/bridges DONE ##########\n")


# ############################################################################
#                                                                            #
#   Retrieve VLANs Associated from bridge_normal                             #
#                                                                            #
# ############################################################################
@mark.gate
def test_ops_restd_ft_vlans_get_vlans_associated(setup, sanity_check,
                                                 topology, step):
    path = "/rest/v1/system/bridges"
    vlan_id = 2
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    expected_data = "%s/%s" % (vlan_path, vlan_name)
    path = vlan_path

    # Creating fake vlan
    create_fake_vlan(vlan_path, switch_ip, vlan_name, vlan_id)

    step("\n########## Executing GET to /system/bridges/{id}/vlans "
         "(VLAN added) ##########\n")
    step("Testing path: %s\n" % path)

    response_status, response_data = execute_request(
        path, "GET", None, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.OK, \
        "Response status received: %s\n" % response_status
    step("Response status received: %s\n" % response_status)

    assert expected_data in get_json(response_data), \
        "Response data received: %s\n" % response_data
    step("Response data received: %s" % response_data)

    step("########## Executing GET to /system/bridges/{id}/vlans "
         "(VLAN added) DONE ##########\n")


# ############################################################################
#                                                                            #
#   Retrieve VLAN by name from bridge_normal                                 #
#                                                                            #
# ############################################################################
@mark.gate
def test_ops_restd_ft_vlans_get_vlan_by_name(setup, sanity_check,
                                             topology, step):
    path = "/rest/v1/system/bridges"
    vlan_id = 2
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    path = "%s/%s" % (vlan_path, vlan_name)

    fake_data = create_fake_vlan(vlan_path, switch_ip, vlan_name, vlan_id)

    swagger_model_verification(switch.container_id,
                               "/system/bridges/{pid}/vlans/{id}",
                               "GET_ID", fake_data, switch_ip)

    expected_configuration_data = {}
    expected_configuration_data["name"] = "%s" % vlan_name
    expected_configuration_data["id"] = vlan_id
    expected_configuration_data["description"] = "test_vlan"
    expected_configuration_data["admin"] = "up"
    # expected_configuration_data["other_config"] = {}
    # expected_configuration_data["external_ids"] = {}

    step("\n########## Executing GET to /system/bridges/{id}/vlans/ "
         "{id} ##########\n")
    step("Testing path: %s\n" % path)

    response_status, response_data = execute_request(
        path, "GET", None, switch_ip, xtra_header=cookie_header)

    expected_response = get_json(response_data)

    assert response_status == http.client.OK, \
        "Response status received: %s\n" % response_status
    step("Response status received %s" % response_status)

    assert compare_dict(expected_response["configuration"],
                        expected_configuration_data), \
        "Response data received: %s\n" % response_data

    step("########## Executing GET to /system/bridges/{id}/vlans/{id} "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Retrieve VLAN by name not associated from bridge_normal                  #
#                                                                            #
# ############################################################################
@mark.gate
def test_ops_restd_ft_vlans_get_non_existent_vlan(setup, sanity_check,
                                                  topology, step):
    path = "/rest/v1/system/bridges"
    vlan_name = "not_found"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    path = "%s/%s" % (vlan_path, vlan_name)

    step("\n########## Executing GET to /system/bridges/{id}/vlans/{id} "
         "##########\n")
    step("Testing path: %s\n" % path)

    response_status, response_data = execute_request(
        path, "GET", None, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.NOT_FOUND, \
        "Response status received: %s\n" % response_status
    step("Response status received: %s\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data == "", \
        "Response data received: %s" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing GET to /system/bridges/{id}/vlans/{id} "
         "DONE ##########\n")
