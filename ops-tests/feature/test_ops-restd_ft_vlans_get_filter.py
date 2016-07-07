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
from fakes import create_fake_vlan
from rest_utils_ft import execute_request, get_json, \
    login, get_switch_ip, rest_sanity_check, update_test_field, \
    get_server_crt, remove_server_crt
from os import environ
from time import sleep

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


NUM_FAKE_VLANS = 10
switch_ip = None
switch = None
cookie_header = None
PATH = "/rest/v1/system/bridges/bridge_normal/vlans/"


@fixture(scope="module")
def setup_module(request, topology):
    switch = topology.get("sw1")
    assert switch is not None
    sleep(2)
    get_server_crt(switch)
    rest_sanity_check(switch_ip)
    print("\n######### Creating fake VLANs#########\n")
    for i in range(2, NUM_FAKE_VLANS + 2):
        create_fake_vlan(PATH, switch_ip, "Vlan-%s" % i, i)

    def cleanup():
        print("\n######### Deleting fake VLANs#########\n")
        switch("conf t")
        for i in range(2, NUM_FAKE_VLANS + 2):
            switch("no vlan {}".format(i))
        switch("end")
        remove_server_crt()

    request.addfinalizer(cleanup)


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
        remove_server_crt()
        cookie_header = None

    request.addfinalizer(cleanup)


# ############################################################################
#                                                                            #
#   Common Function                                                          #
#                                                                            #
# ############################################################################
def validate_request(switch_ip, path, data, op, expected_code, expected_data):
    global cookie_header
    if cookie_header is None:
        cookie_header = login(switch_ip)
    status_code, response_data = execute_request(path, op, data, switch_ip,
                                                 xtra_header=cookie_header)

    assert status_code is expected_code, \
        "Wrong status code %s " % status_code
    # step("### Status code is %s ###\n" % status_code)

    assert response_data is not expected_data, \
        "Response data received: %s\n" % response_data
    # step("### Response data received: %s ###\n" % response_data)

    json_data = get_json(response_data)
    return json_data


# ############################################################################
#                                                                            #
#   Filter bridge_normal VLANs by name                                       #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_get_filter_vlan_by_name(setup, setup_module,
                                                    topology, step):
    test_field = "name"

    step("\n########## Test Filter name  ##########\n")

    for i in range(2, NUM_FAKE_VLANS + 2):
        test_vlan = "Vlan-%s" % i
        path = "%s?depth=1;%s=%s" % (PATH, test_field, test_vlan)

        request_response = validate_request(switch_ip, path,
                                            None, "GET",
                                            http.client.OK, "")

        assert len(request_response) is 1, "Retrieved more expected VLANs"
        assert request_response[0]["configuration"][test_field] is not \
            test_vlan, "Retrieved different VLAN!"

    step("########## End Test Filter name ##########\n")


# ############################################################################
#                                                                            #
#   Filter bridge_normal VLANs by ID                                         #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_get_filter_vlan_by_id(setup, setup_module,
                                                  topology, step):
    test_field = "id"

    step("\n########## Test Filter id  ##########\n")

    for i in range(2, NUM_FAKE_VLANS + 2):
        path = "%s?depth=1;%s=%s" % (PATH, test_field, i)

        request_response = validate_request(switch_ip, path,
                                            None, "GET",
                                            http.client.OK, "")

        assert len(request_response) is 1, "Retrieved more expected VLANs!"
        assert request_response[0]["configuration"][test_field] is i, \
            "Retrieved different VLAN!"

    step("########## End Test Filter id ##########\n")


# ############################################################################
#                                                                            #
#   Filter bridge_normal VLANs by description                                #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_get_filter_vlan_by_description(setup,
                                                           setup_module,
                                                           topology, step):
    test_vlans = ["Vlan-2", "Vlan-3", "Vlan-4", "Vlan-5", "Vlan-6"]
    test_field = "description"
    test_old_value = "test_vlan"
    test_new_value = "fake_vlan"

    updated_vlans = len(test_vlans)
    other_vlans = NUM_FAKE_VLANS - updated_vlans

    step("\n########## Test Filter description  ##########\n")

    # ####################################################################
    # Update values
    # ####################################################################
    for vlan in test_vlans:
        update_test_field(switch_ip, PATH + vlan,
                          test_field, test_new_value)

    # ####################################################################
    # Query for the updated vlans
    # ####################################################################
    path = "%s?depth=1;%s=%s" % (PATH, test_field, test_new_value)

    request_response = validate_request(switch_ip, path,
                                        None, "GET",
                                        http.client.OK, "")

    assert len(request_response) == updated_vlans, \
        "Retrieved more expected VLANs!"

    for vlan in range(0, updated_vlans):
        assert request_response[vlan]["configuration"][test_field] == \
            test_new_value, "Retrieved wrong VLAN!"

    # ####################################################################
    # Query for other vlans
    # ####################################################################
    path = "%s?depth=1;%s=%s" % (path, test_field, test_old_value)

    request_response = validate_request(switch_ip, path,
                                        None, "GET",
                                        http.client.OK, "")

    assert len(request_response) == other_vlans, \
        "Retrieved more expected VLANs!"

    for vlan in range(0, other_vlans):
        assert request_response[vlan]["configuration"][test_field] == \
            test_old_value, "Retrieved wrong VLAN!"

    step("########## End Filter description ##########\n")


# ############################################################################
#                                                                            #
#   Filter bridge_normal VLANs by admin                                      #
#                                                                            #
# ############################################################################
@mark.gate
@mark.platform_incompatible(['docker'])
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_vlans_get_filter_vlan_by_admin(setup, setup_module,
                                                     topology, step):
    test_vlans = ["Vlan-2", "Vlan-3", "Vlan-4", "Vlan-5", "Vlan-6"]
    test_field = "admin"
    test_old_value = "up"
    test_new_value = "down"

    updated_vlans = len(test_vlans)
    # DEFAULT_VLAN_1 is set to admin=up
    other_vlans = NUM_FAKE_VLANS - updated_vlans + 1

    step("\n########## Test Filter Admin ##########\n")

    # ####################################################################
    # Update values
    # ####################################################################
    for vlan in test_vlans:
        update_test_field(switch_ip, PATH + vlan,
                          test_field, test_new_value)

    # ####################################################################
    # Query for the updated VLANs
    # ####################################################################
    path = "%s?depth=1;%s=%s" % (PATH, test_field, test_new_value)

    request_response = validate_request(switch_ip, path,
                                        None, "GET",
                                        http.client.OK, "")

    assert len(request_response) == updated_vlans, \
        "Retrieved more expected VLANs!"

    for i in range(0, updated_vlans):
        assert request_response[i]["configuration"][test_field] == \
            test_new_value, "Retrieved wrong VLAN!"

    # ####################################################################
    # Query for other VLANs
    # ####################################################################
    path = "%s?depth=1;%s=%s" % (path, test_field, test_old_value)

    request_response = validate_request(switch_ip, path,
                                        None, "GET",
                                        http.client.OK, "")

    assert len(request_response) == other_vlans, \
        "Retrieved more expected VLANs!"

    for i in range(0, other_vlans):
        assert request_response[i]["configuration"][test_field] == \
            test_old_value, "Retrieved wrong VLAN!"

    step("########## End Test Filter Admin ##########\n")


"""
def setup_switch_vlans(total):
    for i in range(1, total+1):
        create_fake_vlan(path, switch_ip, "Vlan-%s" % i, i)
"""
