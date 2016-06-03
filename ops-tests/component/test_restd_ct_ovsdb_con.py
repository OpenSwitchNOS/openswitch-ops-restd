# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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

from pytest import fixture

from rest_utils import execute_request, get_switch_ip, get_json, \
    rest_sanity_check, login, get_container_id

import json
import http.client
import copy
from time import sleep
from os import environ
from operator import itemgetter
from subprocess import call


# Topology definition. the topology contains two back to back switches
# having four links between them.


TOPOLOGY = """
# +-------+     +-------+
# |  sw1  <----->  hs1  |
# +-------+     +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=oobmhost name="Host 1"] hs1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- hs1:1
"""


path_system = '/rest/v1/system'


SWITCH_IP = None
cookie_header = None
proxy = None
sw1 = None


@fixture()
def setup(request, topology):
    global cookie_header
    global SWITCH_IP
    global proxy
    global sw1
    sw1 = topology.get("sw1")
    assert sw1 is not None
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(sw1)
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)
    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None

    request.addfinalizer(cleanup)


@fixture(scope="module")
def sanity_check():
    sleep(2)
    rest_sanity_check(SWITCH_IP, cookie_header)


def test_restd_ct_ovsdb_con_stop_ovsdb_server(setup, sanity_check,
                                              topology, step):

    step("\n#####################################################\n")
    step("#           Stopping the OVSDB-SERVER               #")
    step("\n#####################################################\n")

    sw1("systemctl stop ovsdb-server", shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "inactive" == is_active
    sleep(2)

    count = 0
    while (count < 15):
        step("\nExecuting GET request\n")
        status_code, response_data = execute_request(
            path_system, "GET", None, SWITCH_IP, False,
            xtra_header=cookie_header)
        sleep(1)

        count = count + 1
        step("Try " + str(count) + "/15 to execute GET request")
        if status_code == http.client.SERVICE_UNAVAILABLE:
            break

    assert status_code == http.client.SERVICE_UNAVAILABLE

    sw1("systemctl start ovsdb-server", shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "active" == is_active
    sleep(1)


def test_restd_ct_ovsdb_con_stop_start_ovsdb_server(setup, sanity_check,
                                                    topology, step):

    step("\n#####################################################\n")
    step("#       Stop/start the OVSDB-SERVER      #")
    step("\n#####################################################\n")

    ovsdbs_pid = sw1("pgrep -f /usr/sbin/ovsdb-server", shell="bash")
    sw1("kill -11 " + ovsdbs_pid, shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "activating" == is_active
    sleep(2)

    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "active" == is_active
    sleep(1)

    count = 0
    while (count < 15):
        step("\nExecuting GET request\n")
        status_code, response_data = execute_request(
            path_system, "GET", None, SWITCH_IP, False,
            xtra_header=cookie_header)
        sleep(1)
        count = count + 1
        step("Try " + str(count) + "/15 to execute GET request")
        if status_code == http.client.OK:
            break

    assert status_code == http.client.OK


def test_restd_ct_ovsdb_con_stop_ovsdb_server_start_stop_restd(
        setup, sanity_check, topology, step):

    step("\n#####################################################\n")
    step("#       Stopping OVSDB-SERVER and stop/start Restd  #")
    step("\n#####################################################\n")

    sw1("systemctl stop ovsdb-server", shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "inactive" == is_active
    sleep(1)

    restd_pid = sw1("pgrep -f restd", shell="bash")
    sw1("kill " + restd_pid, shell="bash")
    is_active = sw1("systemctl is-active restd", shell="bash")
    assert "activating" == is_active
    sleep(2)

    is_active = sw1("systemctl is-active restd", shell="bash")
    assert "active" == is_active
    sleep(1)

    count = 0
    while (count < 15):
        step("\nExecuting GET request\n")
        status_code, response_data = execute_request(
            path_system, "GET", None, SWITCH_IP, False,
            xtra_header=cookie_header)
        sleep(1)
        count = count + 1
        step("Try " + str(count) + "/15 to execute GET request")
        if status_code == http.client.SERVICE_UNAVAILABLE:
            break

    assert status_code == http.client.SERVICE_UNAVAILABLE

    sw1("systemctl start ovsdb-server", shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "active" == is_active
    sleep(1)


def test_restd_ct_ovsdb_con_stop_start_server_start_stop_restd(
        setup, sanity_check, topology, step):

    step("\n#####################################################\n")
    step("#       Stop/start OVSDB-SERVER and stop/start Restd  #")
    step("\n#####################################################\n")

    ovsdbs_pid = sw1("pgrep -f /usr/sbin/ovsdb-server", shell="bash")
    sw1("kill -11 " + ovsdbs_pid, shell="bash")
    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "activating" == is_active
    sleep(3)

    is_active = sw1("systemctl is-active ovsdb-server", shell="bash")
    assert "active" == is_active

    restd_pid = sw1("pgrep -f restd", shell="bash")
    sw1("kill " + restd_pid, shell="bash")
    is_active = sw1("systemctl is-active restd", shell="bash")
    assert "activating" == is_active
    sleep(3)

    is_active = sw1("systemctl is-active restd", shell="bash")
    assert "active" == is_active
    sleep(3)

    count = 0
    while (count < 15):
        step("\nExecuting GET request\n")
        status_code, response_data = execute_request(
            path_system, "GET", None, SWITCH_IP, False,
            xtra_header=cookie_header)
        sleep(1)
        count = count + 1
        step("Try " + str(count) + "/15 to execute GET request")
        if status_code == http.client.OK:
            break

    assert status_code == http.client.OK
