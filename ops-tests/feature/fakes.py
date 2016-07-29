#!/usr/bin/env python
#
# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rest_utils_ft import login, execute_request
import http.client
import json
from rest_utils_physical_ft import CRT_DIRECTORY_HS, HTTP_CREATED


FAKE_PORT_DATA = """
{
    "configuration": {
        "name": "Port-%(index)s",
        "interfaces": ["/rest/v1/system/interfaces/1"],
        "ip4_address_secondary": ["192.168.1.%(index)s/24"],
        "lacp": ["active"],
        "bond_mode": ["l2-src-dst-hash"],
        "ip6_address": ["2001:0db8:85a3:0000:0000:8a2e:0370:%(index)04d/64"],
        "external_ids": {"extid1key": "extid1value"},
        "mac": ["01:23:45:67:89:%(index)02x"],
        "other_config": {"cfg-1key": "cfg1val"},
        "bond_active_slave": "null",
        "ip6_address_secondary": \
        ["2001:0db8:85a3:0000:0000:8a2e:0371:%(index)04d/64"],
        "ip4_address": "192.168.0.%(index)s/24",
        "admin": "up",
        "qos_config": {"qos_trust": "none"},
        "ospf_auth_text_key": "null",
        "ospf_auth_type": "null",
        "ospf_if_out_cost": 10,
        "ospf_mtu_ignore": false,
        "ospf_priority": 0,
        "ospf_if_type": "ospf_iftype_broadcast",
        "ospf_intervals": {"transmit_delay": 1}
    },
    "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
}
"""

FAKE_VLAN_DATA = """
{
    "configuration": {
        "name": "%(name)s",
        "id": %(id)s,
        "description": "test_vlan",
        "admin": ["up"],
        "other_config": {},
        "external_ids": {}
    }
}
"""

FAKE_BRIDGE_DATA = """
{
    "configuration": {
        "name": "%s",
        "ports": [],
        "vlans": [],
        "datapath_type": "",
        "other_config": {
            "hwaddr": "",
            "mac-table-size": "16",
            "mac-aging-time": "300"
        },
        "external_ids": {}
     }
}
"""


def create_fake_port(path, switch_ip, port_index, cookie_header=None):
    if cookie_header is None:
        cookie_header = login(switch_ip)

    data = FAKE_PORT_DATA % {"index": port_index}

    print("\n---------- Creating fake port (%s) ----------\n" %
          port_index)
    print("Testing path: %s\nTesting data: %s\n" % (path, data))

    response_status, response_data = execute_request(
        path, "POST", data, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.CREATED, \
        "Response status received: %s\n" % response_status
    print("Fake port \"%s\" created!\n" % port_index)

    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    print("Response data: %s\n" % response_data)
    print("---------- Creating fake port (%s) DONE ----------\n" %
          port_index)


def create_fake_port_ostl(path, port_index, hs1, step, login_result,
                          cookie_header=None):
    data = FAKE_PORT_DATA % {"index": port_index}

    print("\n---------- Creating fake port (%s) ----------\n" %
          port_index)
    print("Testing path: %s\nTesting data: %s\n" % (path, data))

    post_result = hs1.libs.openswitch_rest.system_ports_post(
        json.loads(data),
        https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)

    status_code = post_result.get('status_code')
    print("\nstatus code post result --> %s\n" % status_code)
    assert status_code == HTTP_CREATED, \
        "Response status received: %s\n" % status_code

    print("---------- Creating fake port (%s) DONE ----------\n" %
          port_index)


def create_fake_vlan(path, switch_ip, fake_vlan_name, vlan_id,
                     cookie_header=None):
    if cookie_header is None:
        cookie_header = login(switch_ip)

    data = FAKE_VLAN_DATA % {"name": fake_vlan_name, "id": vlan_id}

    print("\n---------- Creating fake vlan (%s) ----------\n" %
          fake_vlan_name)
    print("Testing Path: %s\nTesting Data: %s\n" % (path, data))

    response_status, response_data = execute_request(
        path, "POST", data, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.CREATED, \
        "Response status received: %s\n" % response_status
    print("Fake VLAN \"%s\" created!\n" % fake_vlan_name)
    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    print("Response data received: %s\n" % response_data)
    print("---------- Creating fake vlan (%s) DONE ----------\n" %
          fake_vlan_name)


def create_fake_bridge(path, switch_ip, fake_bridge_name, cookie_header=None):
    if cookie_header is None:
        cookie_header = login(switch_ip)

    data = FAKE_BRIDGE_DATA % fake_bridge_name

    print("\n---------- Creating fake bridge (%s) ----------\n" %
          fake_bridge_name)
    print("Testing path: %s\nTesting data: %s\n" % (path, data))

    response_status, response_data = execute_request(
        path, "POST", data, switch_ip, xtra_header=cookie_header)

    assert response_status == http.client.CREATED, \
        "Response status: %s\n" % response_status
    print("Bridge \"%s\" created!\n" % fake_bridge_name)
    if isinstance(response_data, bytes):
        response_data = response_data.decode("utf-8")
    assert response_data is "", \
        "Response data received: %s\n" % response_data
    print("Response data received: %s\n" % response_data)
    print("---------- Creating fake bridge (%s) DONE ----------\n" %
          fake_bridge_name)
