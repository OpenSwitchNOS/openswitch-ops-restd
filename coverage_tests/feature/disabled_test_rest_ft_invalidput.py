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
    rest_sanity_check, login, get_server_crt, remove_server_crt

from time import sleep
from json import dumps as json_dumps

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
proxy = None
url_system = "/rest/v1/system/"
url_interfaces = "/rest/v1/system/interfaces/1"
DATA = {
    "configuration": {
        "bridges": ["/rest/v1/system/bridge_normal"],
        "lacp_config": {},
        "dns_servers": [],
        "aaa": {
            "ssh_publickeyauthentication": "enable",
            "fallback": "true",
            "radius": "false",
            "ssh_passkeyauthentication": "enable"},
        "logrotate_config": {},
        "hostname": "openswitch",
        "manager_options": [],
        "subsystems": ["/rest/v1/system/base"],
        "asset_tag_number": "",
        "ssl": [],
        "mgmt_intf": {
            "ip": "10.10.10.2",
            "subnet-mask": '24',
            "mode": "static",
            "name": "eth0",
            "default-gateway": ""},
        "radius_servers": [],
        "management_vrf": [],
        "other_config": {
            "enable-statistics": "true"},
        "daemons": [
            "/rest/v1/system/fan",
            "/rest/v1/system/power",
            "/rest/v1/system/sys",
            "/rest/v1/system/led",
            "/rest/v1/system/pm",
            "/rest/v1/system/temp"],
        "bufmon_config": {},
        "external_ids": {},
        "ecmp_config": {},
        "vrfs": ["/rest/v1/system/vrf"]}}
PUT_DATA = {
    "configuration": {
        "split_parent": ["/rest/v1/system/interfaces/1"],
        "name": "1",
        "other_config": {},
        "user_config": {},
        "split_children": [],
        "external_ids": {},
        "type": "integer",
        "options": {}}}


def _netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def _invalid_put_method():
    status_code, response_data = execute_request(
        url_system, "PUT", json_dumps(DATA),
        SWITCH_IP, False, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST

    status_code, response_data = execute_request(
        url_system, "PUT", json_dumps(PUT_DATA),
        SWITCH_IP, False, xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST


def _setup():
    get_server_crt(switch)
    rest_sanity_check(SWITCH_IP)


def _teardown():
    remove_server_crt()


def test_rest_ft_invalidput(topology):
    global switch
    switch = topology.get("sw1")
    assert switch is not None
    global SWITCH_IP
    SWITCH_IP = get_switch_ip(switch)
    _setup()
    _netop_login()

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

    switch("systemctl stop " + daemon_name, shell="bash")
    switch("cd " + dir, shell="bash")
    switch("coverage run -a --source=" + src_dir_name + " " + file_name +  " &", shell="bash")
    sleep(10)

    _invalid_put_method()
    _teardown()

    switch("cd " + dir, shell="bash")
    switch("ps -ef | grep " + daemon_name + " | grep -v grep | awk '{print $2}' | xargs kill -2", shell="bash")
    switch("cp .coverage " + dir_name + "/coverage_report/.coverage", shell="bash")
    switch("systemctl start " + daemon_name, shell="bash")
    sleep(10)
