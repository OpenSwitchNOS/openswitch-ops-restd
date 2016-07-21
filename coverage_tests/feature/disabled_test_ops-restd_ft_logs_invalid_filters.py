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


from rest_utils_ft import execute_request, login, get_json, \
    get_switch_ip, rest_sanity_check, get_server_crt, remove_server_crt

from pytest import fixture
from os import environ
from time import sleep
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
PATH = "/rest/v1/logs"
logs_path = PATH
cookie_header = None
switch = None
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


def test_ops_restd_ft_logs_invalid_filters(setup, sanity_check,
                                           topology, step):
    global switch
    switch = topology.get("sw1")
    assert switch is not None

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

    step("\n########## Test to Validate logs with invalid filters \
          ##########\n")

    valid_filter = "priority"
    invalid_filter = "priory"

    logs_path = (PATH + "?%s=7&offset=%s&limit=%s") % \
        (valid_filter, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK

    assert response_data is not None

    logs_path = (PATH + "?%s=7&offset=%s&limit=%s") % \
        (invalid_filter, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST

    json_data = get_json(response_data)
    assert len(json_data) <= LIMIT_TEST


def test_ops_restd_ft_logs_invalid_data(setup, sanity_check,
                                        topology, step):
    step("\n########## Test to Validate logs with invalid data for filters\
           ##########\n")

    priority_valid = 7
    priority_invalid = 8

    logs_path = (PATH + "?priority=%s&offset=%s&limit=%s") % \
        (priority_valid, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.OK

    assert response_data is not None

    logs_path = (PATH + "?priority=%s&offset=%s&limit=%s") % \
        (priority_invalid, OFFSET_TEST, LIMIT_TEST)
    status_code, response_data = execute_request(
        logs_path, "GET", None, SWITCH_IP,
        xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST

    json_data = get_json(response_data)
    assert len(json_data) <= LIMIT_TEST

    global switch
    switch = topology.get("sw1")
    assert switch is not None

    switch("cd " + dir, shell="bash")
    switch("ps -ef | grep " + daemon_name + " | grep -v grep | awk '{print $2}' | xargs kill -2", shell="bash")
    switch("cp .coverage " + dir_name + "/coverage_report/.coverage", shell="bash")
    switch("cd coverage_report", shell="bash")
    switch("coverage report -m > cov_report_file.txt", shell="bash")
    switch("systemctl start " + daemon_name, shell="bash")
    sleep(10)
