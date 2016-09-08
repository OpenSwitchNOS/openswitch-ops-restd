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

import os
import http.client
from json import dumps as json_dumps
from rest_utils_ft import execute_request, login, get_json, \
    get_switch_ip, get_server_crt, remove_server_crt
from pytest import mark

# Topology definition. the topology contains two back to back switches
# having four links between them.

TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
"""

cookie_header = None
SWITCH_IP = None
switch = None


def ordered(obj):
    if isinstance(obj, dict):
        return sorted((k, ordered(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered(x) for x in obj)
    else:
        return obj


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _verify_startup_config():
    print('''"\n########## Verify startup config writes and reads the
         config to startup config db ##########\n"''')

    src_path = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(src_path, 'json.data')

    path = '/rest/v1/system/full-configuration?type=startup'
    with open(src_file) as data_file:
        _data = get_json(data_file.read())

    status_code, response_data = execute_request(
        path, "PUT", json_dumps(_data), SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK

    status_code, response_data = execute_request(
        path, "GET", None, SWITCH_IP, xtra_header=cookie_header)
    content = get_json(response_data)

    assert status_code == http.client.OK

    assert ordered(content) == ordered(_data)


def _setup():
    get_server_crt(switch)


def _teardown():
    remove_server_crt()


@mark.gate
def test_ops_restd_ft_runconfig_rest(topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup()
    _netop_login()
    _verify_startup_config()
    _teardown()
