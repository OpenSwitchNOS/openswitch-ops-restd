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

from pytest import fixture

from rest_utils import (
    execute_request, get_switch_ip,
    get_json, rest_sanity_check, login
)

import json
import http.client
from time import sleep
from os import environ
from operator import itemgetter


# Topology definition. the topology contains two back to back switches
# having four links between them.


TOPOLOGY = """
# +-------+     +-------+
# |  sw1  <----->  hs1  |
# +-------+     +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=oobmhost name="Host 1"] hs1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- hs1:1
"""

'''

This test verifies that the default rows in vrf, bridge and vlan are
not deleted via REST. It also verifies that the physical interfaces
are not deleted via a REST DELETE request

'''
path_id_interface = '/rest/v1/system/interfaces/1'
path_id_interface_1 = '/rest/v1/system/interfaces/bridge_normal'
path_id_default_bridge = '/rest/v1/system/bridges/bridge_normal'
path_id_default_vrf = '/rest/v1/system/vrfs/vrf_default'
path_id_default_vlan = '/rest/v1/system/bridges/bridge_normal/vlans/DEFAULT_VLAN_1'

SWITCH_IP = None
cookie_header = None
proxy = None


@fixture()
def setup(request, topology):
    global cookie_header
    global SWITCH_IP
    global proxy
    sw1 = topology.get("sw1")
    assert sw1 is not None
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(sw1)
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        environ["https_proxy"] = proxy


@fixture(scope="module")
def sanity_check():
    sleep(2)
    rest_sanity_check(SWITCH_IP)


def test_restd_ct_invalid_delete_interfaces(setup, sanity_check,
                                            topology, step):

    step("\n#####################################################\n")
    step("#         Testing DELETE for System Interfaces          #")
    step("\n#####################################################\n")

    # DELETE the interface
    status_code, response_data = execute_request(
        path_id_interface, "DELETE", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.BAD_REQUEST

    # GET after deleting the interface
    status_code, response_data = execute_request(
        path_id_interface, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK


def test_restd_ct_valid_delete_interfaces(setup, sanity_check,
                                          topology, step):

    step("\n#####################################################\n")
    step("#      Testing DELETE for non system Interfaces         #")
    step("\n#####################################################\n")

    # DELETE the interface
    status_code, response_data = execute_request(
        path_id_interface_1, "DELETE", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.NO_CONTENT

    # GET after deleting the interface
    status_code, response_data = execute_request(
        path_id_interface_1, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.NOT_FOUND


def test_restd_ct_invalid_delete_default_vrf(setup, sanity_check,
                                             topology, step):

    step("\n#####################################################\n")
    step("#         Testing DELETE for Default vrf                #")
    step("\n#####################################################\n")

    # DELETE the default vlan
    status_code, response_data = execute_request(
        path_id_default_vrf, "DELETE", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.BAD_REQUEST

    # GET after deleting the default vlan
    status_code, response_data = execute_request(
        path_id_default_vrf, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK


def test_restd_ct_invalid_delete_default_bridge(setup, sanity_check,
                                                topology, step):

    step("\n#####################################################\n")
    step("#         Testing DELETE for Default bridge             #")
    step("\n#####################################################\n")

    # DELETE the default bridge
    status_code, response_data = execute_request(
        path_id_default_bridge, "DELETE", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.BAD_REQUEST

    # GET after deleting the default bridge
    status_code, response_data = execute_request(
        path_id_default_bridge, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK


def test_restd_ct_invalid_delete_default_vlan(setup, sanity_check,
                                              topology, step):

    step("\n#####################################################\n")
    step("#         Testing DELETE for Default VLAN               #")
    step("\n#####################################################\n")
    # DELETE the default vlan
    status_code, response_data = execute_request(
        path_id_default_vlan, "DELETE", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.BAD_REQUEST

    # GET after deleting the default vlan
    status_code, response_data = execute_request(
        path_id_default_vlan, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK
