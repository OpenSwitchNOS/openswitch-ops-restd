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


TRUNCATE_ENTRIES = 1000

SWITCH_IP = None
switch = None
# get_switch_ip(switch)
PATH = "/rest/v1/logs"
LOGS_PATH = PATH
cookie_header = None


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _logs_with_no_filters():
    print("\n########## Test to Validate logs with no filters ##########\n")

    status_code, response_data = execute_request(
        LOGS_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK

    assert response_data is not None

    json_data = get_json(response_data)

    assert len(json_data) <= TRUNCATE_ENTRIES


def _setup():
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)


def _teardown():
    remove_server_crt()


def test_ops_restd_ft_logs_with_no_filters(topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup()
    _netop_login()
    _logs_with_no_filters()
    _teardown()
