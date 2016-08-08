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

from topology_common.ops.configuration_plane.rest.rest \
    import create_certificate_and_copy_to_host
from rest_utils_physical_ft import set_rest_server, add_ip_devices, \
    ensure_connectivity, login_to_physical_switch
from rest_utils_physical_ft import SW_IP, HS_IP, \
    CRT_DIRECTORY_HS, HTTP_OK, HTTP_DELETED

from pytest import fixture, mark
import json
import http.client

from fakes import create_fake_vlan
from rest_utils_ft import execute_request, login, \
    rest_sanity_check, get_switch_ip, get_server_crt, \
    remove_server_crt
from datetime import datetime
from os import environ
from time import sleep

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
SWITCH_IP = None
switch = None
cookie_header = None
DEFAULT_VLAN = ['/rest/v1/system/bridges/bridge_normal/vlans/DEFAULT_VLAN_1']

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


# ############################################################################
#                                                                            #
#   Basic Delete for non-existent VLAN in OSTL                               #
#                                                                            #
# ############################################################################
def _delete_non_existent_vlan_ostl(login_result, hs1, step):
    path = "/rest/v1/system/bridges"
    vlan_name = "not_found"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    step("\n########## Executing DELETE for %s ##########\n" %
         vlan_path)
    delete_result = \
        hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_delete(
            DEFAULT_BRIDGE, vlan_name,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    assert delete_result.get('status_code') == http.client.NOT_FOUND, \
        "Response status: %s\n" % delete_result.get('status_code')
    step("Response status: \"%s\"\n" % delete_result.get('status_code'))
    get_result = hs1.libs.openswitch_rest.system_bridges_pid_vlans_get(
            DEFAULT_BRIDGE,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    assert get_result.get('status_code') == HTTP_OK
    assert get_result["content"] == DEFAULT_VLAN, \
        "Response data received: %s\n" % get_result.get('status_code')
    step("Response data received: %s\n" % get_result.get('status_code'))

    step("########## Executing DELETE for %s DONE "
         "##########\n" % vlan_path)


# ############################################################################
#                                                                            #
#   Basic Delete for existent VLAN in OSTL                                   #
#                                                                            #
# ############################################################################
def _delete_existent_vlan_ostl(login_result, hs1, step):

    path = "/rest/v1/system/bridges"
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    delete_path = "%s/%s" % (vlan_path, vlan_name)

    # Setting fake VLAN
    hs1.libs.openswitch_rest.system_bridges_pid_vlans_post(
            DEFAULT_BRIDGE, json.loads(VLAN_DATA),
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    #######################################################################
    # DELETE added VLAN
    #######################################################################
    step("\n########## Executing DELETE for %s ##########\n" % delete_path)
    delete_result = \
        hs1.libs.openswitch_rest.system_bridges_pid_vlans_id_delete(
            DEFAULT_BRIDGE, vlan_name,
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)

    assert delete_result.get('status_code') == HTTP_DELETED
    step("Response status: \"%s\"\n" % delete_result.get('status_code'))

    step("########## Executing DELETE for %s DONE "
         "##########\n" % delete_path)

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
    assert get_result["content"] == DEFAULT_VLAN
    step("Response status received: \"%s\"\n" % get_result.get('status_code'))

    step("########## Executing GET for %s DONE "
         "##########\n" % vlan_path)


@mark.gate
@mark.platform_incompatible(['docker'])
def test_rest_ft_vlans_delete_ostl(topology, step):
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
    _delete_existent_vlan_ostl(login_result, hs1, step)
    _delete_non_existent_vlan_ostl(login_result, hs1, step)


@fixture(scope="module")
def sanity_check():
    sleep(2)
    rest_sanity_check(SWITCH_IP)


@fixture()
def setup(request, topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(switch)
    global proxy
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switch)
    global cookie_header
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None
        remove_server_crt()

    request.addfinalizer(cleanup)


# ############################################################################
#                                                                            #
#   Basic Delete for non-existent VLAN                                       #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_delete_non_existent_vlan(setup, sanity_check,
                                                     topology, step):
    path = "/rest/v1/system/bridges"
    vlan_name = "not_found"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    delete_path = "%s/%s" % (vlan_path, vlan_name)
    step("\n########## Executing DELETE for %s ##########\n" %
         vlan_path)

    response_status, response_data = execute_request(
        delete_path, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert response_status == http.client.NOT_FOUND, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing DELETE for %s DONE "
         "##########\n" % vlan_path)


# ############################################################################
#                                                                            #
#   Basic Delete for existent VLAN                                           #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_delete_existent_vlan(setup, sanity_check,
                                                 topology, step):
    path = "/rest/v1/system/bridges"
    vlan_id = 2
    vlan_name = "fake_vlan"
    vlan_path = "%s/%s/vlans" % (path, DEFAULT_BRIDGE)
    delete_path = "%s/%s" % (vlan_path, vlan_name)
    # Setting fake VLAN
    create_fake_vlan(vlan_path, SWITCH_IP, vlan_name, vlan_id)
    #######################################################################
    # DELETE added VLAN
    #######################################################################
    step("\n########## Executing DELETE for %s ##########\n" % delete_path)

    response_status, response_data = execute_request(
        delete_path, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert response_status == http.client.NO_CONTENT, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)
    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    step("Response data received: %s\n" % response_data)

    step("########## Executing DELETE for %s DONE "
         "##########\n" % delete_path)

    #######################################################################
    # GET existing VLANs
    #######################################################################
    step("\n########## Executing GET for %s ##########\n" % vlan_path)
    step("Testing Path: %s\n" % vlan_path)

    response_status, response_data = execute_request(
        delete_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert response_status == http.client.NOT_FOUND, \
        "Response status received: %s\n" % response_status
    step("Response status received: \"%s\"\n" % response_status)

    step("########## Executing GET for %s DONE "
         "##########\n" % vlan_path)
