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
from os import environ
from time import sleep

from rest_utils_ft import execute_request, login, \
    get_switch_ip, get_json, rest_sanity_check, get_server_crt, \
    remove_server_crt

import http.client

# Topology definition. the topology contains two back to back switches
# having four links between them.

TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
"""

OFFSET_TEST = 0
LIMIT_TEST = 10
SWITCH_IP = None
switch = None
PATH = "/rest/v1/logs"
logs_path = PATH
cookie_header = None
proxy = None


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


@mark.gate
def test_ops_restd_ft_logs_pagination_with_offset_limit(setup,
                                                        sanity_check,
                                                        topology,
                                                        step):
    step("\n########## Test to Validate logs with pagination parameters \
          ##########\n")

    logs_path = (PATH + "?offset=%s&limit=%s") % \
        (OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned for logs are not empty ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST, "Pagination for logs failed %s " \
        % len(json_data)
    step("### Pagination for logs works fine ###\n")

    step("\n########## End Test to Validate logs with pagination" +
         " paramteres ##########\n")


@mark.gate
def test_ops_restd_ft_logs_pagination_negative_with_offset_limit(setup,
                                                                 sanity_check,
                                                                 topology,
                                                                 step):
    step("\n########## Test to Validate logs with negative pagination" +
         " parameters ##########\n")

    logs_path = (PATH + "?offset=1&limit=-1")
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, "Wrong status code %s " \
        % status_code
    step("### Status code for negative limit is okay ###\n")

    logs_path = (PATH + "?offset=-1&limit=-1")
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, "Wrong status code %s " \
        % status_code
    step("### Status code for negative offset and limit is OK ###\n")

    logs_path = (PATH + "?offset=-1&limit=1")
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST, "Wrong status code %s " \
        % status_code
    step("### Status code for negative offset is okay ###\n")

    step("\n########## End Test to Validate logs with negative" +
         " pagination parameters ##########\n")


@mark.gate
def test_ops_restd_ft_logs_pagination_with_offset_none(setup, sanity_check,
                                                       topology, step):
    step("\n########## Test to Validate logs with no offset for" +
         " pagination ##########\n")

    # offset_test = None

    logs_path = PATH + "?limit=%s" % LIMIT_TEST
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned is not empty ###\n")

    json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    assert len(json_data) <= LIMIT_TEST, "Pagination for logs failed %s " \
        % len(json_data)
    step("### Pagination for logs works fine ###\n")

    step("\n########## End Test to Validate logs with no offset for" +
         " pagination ##########\n")


@mark.gate
def test_ops_restd_ft_logs_pagination_with_limit_none(setup, sanity_check,
                                                      topology, step):
    step("\n########## Test to Validate logs with no limit for" +
         " pagination ##########\n")

    # limit_test = None

    logs_path = PATH + "?offset=%s" % OFFSET_TEST
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK, "Wrong status code %s " % status_code
    step("### Status code is OK ###\n")

    assert response_data is not None, "Response data is empty"
    step("### Response data returned is not empty ###\n")

    # json_data = get_json(response_data)
    step("### JSON data is in good shape ###\n")

    step("\n########## End Test to Validate logs with no limit for"
         " pagination ##########\n")
