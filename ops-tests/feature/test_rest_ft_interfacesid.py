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

from rest_utils_ft import execute_request, get_switch_ip, \
    get_json, rest_sanity_check, login, get_server_crt, \
    remove_server_crt

from json import dumps as json_dumps
from pytest import mark

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

SWITCH_IP = None
switch = None
url = '/rest/v1/system/interfaces/bridge_normal'
cookie_header = None

DATA = {"configuration": {"name": "bridge_normal", "type": "internal",
                          "user_config": {"admin": "up"}}}


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _interfaces_id():
    status_code, response_data = execute_request(
        url, "PUT", json_dumps(DATA),
        SWITCH_IP, False, xtra_header=cookie_header)

    assert status_code == http.client.OK

    status_code, response_data = execute_request(
        url, "GET", None, SWITCH_IP, False,
        xtra_header=cookie_header)

    assert status_code == http.client.OK

    d = get_json(response_data)
    assert d['configuration'] == DATA['configuration']

    assert d['configuration']['name'] == 'bridge_normal'

    status_code, response_data = execute_request(
        url, "DELETE", json_dumps(DATA), SWITCH_IP, False,
        xtra_header=cookie_header)

    assert status_code == http.client.NO_CONTENT

    status_code, response_data = execute_request(
        url, "GET", None, SWITCH_IP, False,
        xtra_header=cookie_header)

    assert status_code == http.client.NOT_FOUND


def _setup():
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)


def _teardown():
    remove_server_crt()


@mark.gate
def test_rest_ft_interfacesid(topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup()
    _netop_login()
    _interfaces_id()
    _teardown()