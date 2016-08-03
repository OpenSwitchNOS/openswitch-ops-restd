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
from topology_common.ops.configuration_plane.rest.rest \
    import create_certificate_and_copy_to_host
from rest_utils_physical_ft import CRT_DIRECTORY_HS, HTTP_OK, SW_IP, HS_IP
from rest_utils_physical_ft import set_rest_server, add_ip_devices, \
    ensure_connectivity, login_to_physical_switch
from json import dumps as json_dumps
from os import environ
from pytest import mark, fixture
from datetime import datetime
import http.client

# Topology definition. the topology contains two back to back switches
# having four links between them.

TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=host name="Host 1"] hs1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- hs1:1
"""

SWITCH_IP = None
# get_switch_ip(switch)
switch = None
url = "/rest/v1/system"
cookie_header = None
proxy = None
DATA = None
h1 = None
login_result = None

DATA = {
        "configuration": {
            "bridges": ["/rest/v1/system/bridges/bridge_normal"],
            "aaa": {
                "fallback": "true",
                "radius": "false"},
            "hostname": "openswitch",
            "asset_tag_number": " ",
            "mgmt_intf": {
                "ip": SW_IP,
                "subnet_mask": '24',
                "mode": "static",
                "name": "eth1"},
            "other_config": {
                "enable-statistics": "true"},
            "vrfs": ["/rest/v1/system/vrfs/vrf_default"]}}


@fixture()
def setup_module_physical(topology, step):
    s1 = topology.get('sw1')
    h1 = topology.get('hs1')

    date = str(datetime.now())
    s1.send_command('date --set="%s"' % date, shell='bash')

    global login_result, h1

    assert s1 is not None
    assert h1 is not None

    if login_result is None:
        add_ip_devices(s1, h1, step)
        ensure_connectivity(h1, step)
        set_rest_server(h1, step)
        create_certificate_and_copy_to_host(s1, SW_IP, HS_IP, step=step)
        login_result = login_to_physical_switch(h1, step)


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _system():
    status_code, response_data = execute_request(
        url, "PUT", json_dumps(DATA),
        SWITCH_IP, False, xtra_header=cookie_header)
    assert status_code == http.client.OK

    status_code, response_data = execute_request(
        url, "GET", None, SWITCH_IP, False,
        xtra_header=cookie_header)
    assert status_code == http.client.OK

    d = get_json(response_data)

    assert d['configuration']['hostname'] == \
        DATA['configuration']['hostname']

    assert d['configuration']['other_config']['enable-statistics'] == \
        DATA['configuration']['other_config']['enable-statistics']

    assert d['configuration']['mgmt_intf']['mode'] == \
        DATA['configuration']['mgmt_intf']['mode']

    assert d['configuration']['mgmt_intf']['name'] == \
        DATA['configuration']['mgmt_intf']['name']


@mark.gate
@mark.platform_incompatible(['docker'])
def test_system_ostl(topology, step, setup_module_physical):

        put_result = h1.libs.openswitch_rest.system_put(
            DATA, https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
        assert put_result.get('status_code') == HTTP_OK

        get_result = h1.libs.openswitch_rest.system_get(
            https=CRT_DIRECTORY_HS,
            cookies=login_result.get('cookies'),
            request_timeout=5)
        assert get_result.get('status_code') == HTTP_OK

        assert get_result['content']['configuration']['hostname'] == \
            DATA['configuration']['hostname']

        assert get_result['content']['configuration']['other_config']
        ['enable-statistics'] == \
            DATA['configuration']['other_config']
        ['enable-statistics']

        assert get_result['content']['configuration']['mgmt_intf']['mode'] == \
            DATA['configuration']['mgmt_intf']['mode']

        assert get_result['content']['configuration']['mgmt_intf']['name'] == \
            DATA['configuration']['mgmt_intf']['name']


def _setup():
    global proxy
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)
    global DATA
    DATA = {
        "configuration": {
            "bridges": ["/rest/v1/system/bridges/bridge_normal"],
            "aaa": {
                "fallback": "true",
                "radius": "false"},
            "hostname": "openswitch",
            "asset_tag_number": "",
            "mgmt_intf": {
                "ip": SWITCH_IP,
                "subnet_mask": '24',
                "mode": "static",
                "name": "eth0"},
            "other_config": {
                "enable-statistics": "true"},
            "vrfs": ["/rest/v1/system/vrfs/vrf_default"]}}


def _teardown():
    remove_server_crt()
    environ["https_proxy"] = proxy


@mark.gate
@mark.platform_incompatible(['ostl'])
def test_rest_ft_system(topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup()
    _netop_login()
    _system()
    _teardown()
