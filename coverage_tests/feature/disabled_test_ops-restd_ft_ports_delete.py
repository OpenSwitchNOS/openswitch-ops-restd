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


import http.client
from pytest import fixture
from os import environ
from time import sleep

from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, create_test_port, \
    get_server_crt, remove_server_crt, get_json

# Topology definition. the topology contains two back to back switches
# having four links between them.

TOPOLOGY = """
# +-----+
# | sw1 |
# +-----+

# Nodes
[type=openswitch name="Switch 1"] sw1
"""


path = "/rest/v1/system/ports"
port_path = path + "/Port1"
SWITCH_IP = None
PATH = "/rest/v1/system/ports"
PORT_PATH = PATH + "/Port1"
cookie_header = None
switch = None
proxy = None


@fixture(scope="module")
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
    rest_sanity_check(SWITCH_IP)
    # Add a test port
    print("\n########## Creating Test Port  ##########\n")
    status_code, response = create_test_port(SWITCH_IP)
    assert status_code == http.client.CREATED

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None
        remove_server_crt()

    request.addfinalizer(cleanup)


def delete_port_with_depth(step):
    step("\n########## Test delete Port with depth ##########\n")
    status_code, response_data = execute_request(
        PORT_PATH + "?depth=1", "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST


def delete_port(step):
    step("\n########## Test delete Port ##########\n")
    status_code, response_data = execute_request(
        PORT_PATH, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.NO_CONTENT


def verify_deleted_port_from_port_list(step):
    step("\n########## Test Verify if Port is deleted from port list "
         "##########\n")
    # Verify if port has been deleted from the list
    status_code, response_data = execute_request(
        PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    json_data = []

    json_data = get_json(response_data)

    assert port_path not in json_data


def verify_deleted_port(step):
    step("\n########## Test Verify if Port is found ##########\n")
    # Verify deleted port
    status_code, response_data = execute_request(
        PORT_PATH, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.NOT_FOUND


def delete_non_existent_port(step):
    step("\n########## Test delete non-existent Port ##########\n")
    new_path = PATH + "/Port2"
    status_code, response_data = execute_request(
        new_path, "DELETE", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.NOT_FOUND


def test_ops_restd_ft_ports_delete(setup, topology, step):
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
    sw1("coverage run -a --source " + src_dir_name + " " + file_name +  " &", shell="bash")
    sleep(10)

    delete_port_with_depth(step)
    delete_port(step)
    verify_deleted_port_from_port_list(step)
    verify_deleted_port(step)
    delete_non_existent_port(step)

    sw1("cd " + dir, shell="bash")
    sw1("ps -ef | grep " + daemon_name + " | grep -v grep | awk '{print $2}' | xargs kill -2", shell="bash")
    sw1("cp .coverage " + dir_name + "/coverage_report/.coverage", shell="bash")
    sw1("systemctl start " + daemon_name, shell="bash")
    sleep(10)
