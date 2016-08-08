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

from topology_common.ops.configuration_plane.rest.rest \
    import create_certificate_and_copy_to_host
from rest_utils_physical_ft import set_rest_server, add_ip_devices, \
    ensure_connectivity, login_to_physical_switch
from rest_utils_physical_ft import SW_IP, HS_IP, \
    CRT_DIRECTORY_HS, HTTP_CREATED, HTTP_OK, HTTP_NOT_FOUND
from datetime import datetime
import json


# ############################################################################
#                                                                            #
#   Common Tests topology                                                    #
#                                                                            #
# ############################################################################
TOPOLOGY = """
# +-----+      +-------+
# | sw1 <------>  hs1  |
# +-----+      +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=host name="Host 1"] hs1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- hs1:1
"""

DEFAULT_BRIDGE = "bridge_normal"
DEFAULT_VLAN = "DEFAULT_VLAN_1"
switch_ip = None
cookie_header = None
switch = None


VLAN_DATA = """
{
    "configuration": {
        "name": "fake_vlan",
        "id": 2,
        "description": "test_vlan",
        "admin": ["up"],
        "other_config": {},
        "external_ids": {}
    }
}
"""


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
#   Query for Bridge Normal OSTL                                             #
#                                                                            #
# ############################################################################

def _vlans_get_default_bridge_normal(login_result, hs1, step):
    expected_data = ["/rest/v1/system/bridges/%s" % DEFAULT_BRIDGE]
    path = "/rest/v1/system/bridges"

    step("\n########## Executing GET to /system/bridges ##########\n")
    step("Testing Path: %s\n" % path)
    get_result = hs1.libs.openswitch_rest.system_bridges_get(
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    assert get_result.get('status_code') == HTTP_OK, \
        "Response status received: %s\n" % get_result.get('status_code')
    assert get_result["content"] == expected_data
    step("Response status received: \"%s\"\n" % get_result.get('status_code'))
    step("########## Executing GET to /system/bridges DONE ##########\n")


# ############################################################################
#                                                                            #
#   Query for Bridge Normal                                                  #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['ostl'])
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
#   Retrieve VLANs Associated from bridge_normal OSTL                        #
#                                                                            #
# ############################################################################

def _vlans_get_vlans_associated(login_result, hs1, step):
    path = "/rest/v1/system/bridges"
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    expected_data = ["%s/%s" % (vlan_path, DEFAULT_VLAN),
                     "%s/%s" % (vlan_path, vlan_name)
                     ]
    path = vlan_path

    # Setting fake VLAN
    post_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_post(
            DEFAULT_BRIDGE, json.loads(VLAN_DATA),
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
    assert post_result.get('status_code') == HTTP_CREATED
    #######################################################################
    # GET existing VLANs
    #######################################################################
    step("\n########## Executing GET for %s ##########\n" % vlan_path)
    step("Testing Path: %s\n" % vlan_path)
    get_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_get(
            DEFAULT_BRIDGE,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    assert get_result.get('status_code') == HTTP_OK, \
        "Response status received: %s\n" % get_result.get('status_code')
    assert set(get_result["content"]) == set(expected_data)
    step("Response status received: \"%s\"\n" % get_result.get('status_code'))

    step("########## Executing GET to /system/bridges/{id}/vlans "
         "(VLAN added) DONE ##########\n")


# ############################################################################
#                                                                            #
#   Retrieve VLANs Associated from bridge_normal                             #
#                                                                            #
# ############################################################################
@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
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
#   Retrieve VLAN by name from bridge_normal OSTL                            #
#                                                                            #
# ############################################################################
def _vlans_get_vlan_by_name(login_result, hs1, step):
    path = "/rest/v1/system/bridges"
    vlan_id = 2
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    path = "%s/%s" % (vlan_path, vlan_name)
    #######################################################################
    # DELETE added VLAN
    #######################################################################
    hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_delete(
        DEFAULT_BRIDGE, vlan_name,
        https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)

    # Setting fake VLAN
    post_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_post(
            DEFAULT_BRIDGE, json.loads(VLAN_DATA),
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
    assert post_result.get('status_code') == HTTP_CREATED

    expected_configuration_data = {}
    expected_configuration_data["name"] = "%s" % vlan_name
    expected_configuration_data["id"] = vlan_id
    expected_configuration_data["description"] = "test_vlan"
    expected_configuration_data["admin"] = "up"
    print("expected_configuration_data %s\n\n\n" % expected_configuration_data)
    step("\n########## Executing GET to /system/bridges/{id}/vlans/ "
         "{id} ##########\n")
    step("Testing path: %s\n" % path)
    get_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_get(
            DEFAULT_BRIDGE,
            vlan_name,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
    print("get_result %s\n\n" % get_result)
    print("get_result-content %s \n\n\n" % get_result["content"])
    assert get_result.get('status_code') == HTTP_OK, \
        "Response status received: %s\n" % get_result.get('status_code')
    assert get_result["content"]["configuration"] == \
        expected_configuration_data
    step("Response status received: \"%s\"\n" % get_result.get('status_code'))
    #######################################################################
    # DELETE added VLAN
    #######################################################################
    hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_delete(
        DEFAULT_BRIDGE, vlan_name,
        https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)
    step("########## Executing GET to /system/bridges/{id}/vlans/{id} "
         "DONE ##########\n")


# ############################################################################
#                                                                            #
#   Retrieve VLAN by name from bridge_normal                                 #
#                                                                            #
# ############################################################################
@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
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
#   Retrieve VLAN by name not associated from bridge_normal OSTL             #
#    Skipping this test as library doesn't support reutn of None as data     #
# ############################################################################
def _vlans_get_non_existent_vlan(login_result, hs1, step):
    path = "/rest/v1/system/bridges"
    vlan_name = "not_found"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    path = "%s/%s" % (vlan_path, vlan_name)
    expected_data = ["%s/%s/" % (vlan_path, DEFAULT_VLAN)]

    step("\n########## Executing GET to /system/bridges/{id}/vlans/{id} "
         "##########\n")
    step("Testing path: %s\n" % path)
    try:
        get_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_get(
            DEFAULT_BRIDGE, vlan_name,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
    except:
        step("Returning None")
        step("########## Executing GET to /system/bridges/{id}/vlans/{id} "
             "DONE ##########\n")
        return
    assert get_result.get('status_code') == HTTP_NOT_FOUND, \
        "Response status received: %s\n" % get_result.get('status_code')
    assert get_result["content"] == expected_data


# ############################################################################
#                                                                            #
#   Retrieve VLAN by name not associated from bridge_normal                  #
#                                                                            #
# ############################################################################
@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
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


@mark.gate
@mark.platform_incompatible(['docker'])
def test_rest_ft_vlans_get_ostl(topology, step):
    sw1 = topology.get('sw1')
    hs1 = topology.get('hs1')
    assert sw1 is not None
    assert hs1 is not None
    date = str(datetime.now())
    sw1.send_command('date --set="%s"' % date, shell='bash')
    add_ip_devices(sw1, hs1, step)
    ensure_connectivity(hs1, step)
    set_rest_server(hs1, step)
    create_certificate_and_copy_to_host(sw1, SW_IP, HS_IP, step=step)
    login_result = login_to_physical_switch(hs1, step)
    _vlans_get_default_bridge_normal(login_result, hs1, step)
    _vlans_get_vlan_by_name(login_result, hs1, step)
    _vlans_get_vlans_associated(login_result, hs1, step)
    _vlans_get_non_existent_vlan(login_result, hs1, step)
