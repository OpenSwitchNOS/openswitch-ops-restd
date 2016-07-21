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

import http.client

from fakes import create_fake_vlan
from rest_utils_ft import execute_request, login, \
    rest_sanity_check, get_switch_ip, get_server_crt, \
    remove_server_crt

from os import environ
from time import sleep


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
SWITCH_IP = None
switch = None
cookie_header = None


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


def test_ops_restd_ft_vlans_delete_non_existent_vlan(setup, sanity_check,
                                                     topology, step):
    sw1 = topology.get("sw1")
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
def test_ops_restd_ft_vlans_delete_existent_vlan(setup, sanity_check,
                                                 topology, step):
    path = "/rest/v1/system/bridges"
    vlan_id = 1
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

    sw1 = topology.get("sw1")
    assert sw1 is not None

    sw1("cd " + dir, shell="bash")
    sw1("ps -ef | grep " + daemon_name + " | grep -v grep | awk '{print $2}' | xargs kill -2", shell="bash")
    sw1("cp .coverage " + dir_name + "/coverage_report/.coverage", shell="bash")
    sw1("systemctl start " + daemon_name, shell="bash")
    sleep(10)
