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

from rest_utils_ft import (
    get_switch_ip, get_json, remove_server_crt,
    login, execute_request, rest_sanity_check, get_server_crt
)

import http.client
from os import environ

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
cookie_header = None
switch = None
proxy = None
url_vrf = "/rest/v1/system/vrfs"
url_vrf_default = "{}/vrf_default".format(url_vrf)


def _pre_test():
    global proxy
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _vrfs():
    status_code, response_data = execute_request(
        url_vrf, "GET", None,
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK

    d = get_json(response_data)

    assert url_vrf_default in d


def _post_test():
    remove_server_crt()
    global cookie_header
    cookie_header = None
    environ["https_proxy"] = proxy


def test_rest_ft_vrfs(topology):
    global SWITCH_IP
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    SWITCH_IP = get_switch_ip(switch)
    _pre_test()
    _netop_login()
    _vrfs()
    _post_test()
