# -*- coding: utf-8 -*-
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
##########################################################################

from pytest import fixture, mark
from topology_common.ops.configuration_plane.rest.rest \
    import create_certificate_and_copy_to_host

from rest_utils_physical_ft import set_rest_server, add_ip_devices, \
    ensure_connectivity, login_to_physical_switch, SW_IP, HS_IP, \
    CRT_DIRECTORY_HS, HTTP_OK, HTTP_BAD_REQUEST

from rest_utils_ft import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    update_test_field, fill_with_function, random_mac, random_ip6_address,
    get_server_crt, remove_server_crt, update_test_field_ostl
)
from fakes import create_fake_port, create_fake_port_ostl
import random

from os import environ
from time import sleep

import http.client
import json
import inspect
import types
from datetime import datetime

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


SWITCH_IP = None
cookie_header = None
proxy = None
PATH = None
PORT_PATH = None
RESOURCE_NAME = "Port1"

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0
NUM_FAKE_PORTS = 10

switches = []


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy
    cookie_header = None
    sw1 = topology.get("sw1")
    assert sw1 is not None
    switches = [sw1]
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(switches[0])
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(switches[0])
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        cookie_header = None
        remove_server_crt()

    request.addfinalizer(cleanup)


@fixture(scope="module")
def setup_test(topology):
    global PATH, PORT_PATH, RESOURCE_NAME
    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/" + RESOURCE_NAME
    sw1 = topology.get("sw1")
    assert sw1 is not None
    switches = [sw1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)
    setup_switch_ports(NUM_FAKE_PORTS)


def setup_switch_ports_ostl(total, hs1, step, login_result):
    local_path = "/rest/v1/system/ports"
    for i in range(0, total):
        create_fake_port_ostl(local_path, (i + 1), hs1, step, login_result)


def setup_switch_ports(total):
    for i in range(0, total):
        create_fake_port(PATH, SWITCH_IP, (i + 1))


class QuerySortPortTest():
    def execute_sort_by_request(self, attributes, expected_code, desc=False,
                                limit=None, offset=None, depth=1,
                                filters=None):
        """
        Common function to send a sort request
        :param attributes
        :param expected_code
        :param desc
        :param limit:
        :param offset:
        :param depth:
        :param filters
        """
        path = PATH + "?"
        if depth is not None:
            path += "depth=" + str(depth) + ";"
        if limit is not None:
            path += "limit=" + str(limit) + ";"
        if offset is not None:
            path += "offset=" + str(offset) + ";"

        if filters is not None:
            if isinstance(filters, dict):
                for key in filters.keys():
                    path += key + "=" + filters[key]
                path += ";"
            else:
                path += filters[key] + ";"

        path += "sort="

        if desc:
            path += "-"
        if isinstance(attributes, list):
            for attr in attributes:
                path += attr
                if attr != attributes[-1]:
                    path += ","
        else:
            path += attributes

        print("### Request to %s ###\n" % path)
        status_code, response_data = execute_request(
            path, "GET", None, SWITCH_IP, xtra_header=cookie_header)

        assert status_code == expected_code, "Wrong status code %s " % \
                                             status_code
        print("### Status code is %s ###\n" % status_code)
        assert response_data is not "", \
            "Response data received: %s\n" % response_data
        json_data = {}
        try:
            if isinstance(response_data, bytes):
                response_data = response_data.decode("utf-8")
            json_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"

        # In order to no affect the tests the bridge_normal is removed
        if expected_code == http.client.OK:
            self.remove_bridge_from_data(json_data)
        return json_data

    def remove_bridge_from_data(self, json_data):
        """
        Function used to remove the bridge_normal from test data
        """
        index = None
        for i in range(0, len(json_data)):
            if json_data[i]["configuration"]["name"] == "bridge_normal":
                index = i
                break
        if index is not None:
            json_data.pop(index)

    def check_sort_expectations(self, expected_values, json_data, field):
        """
        Common function to check order expectations
        """
        for i in range(0, len(expected_values)):
            # Expected values
            expected_value = expected_values[i]
            # Returned values
            returned_value = json_data[i]["configuration"][field]
            if (isinstance(returned_value, list) and
                    not isinstance(expected_value, list)):
                expected_value = [expected_value]

            assert expected_value == returned_value, "Wrong order. \
                    Expected: %s Returned: %s" % (expected_value,
                                                  returned_value)

    def sort_value_to_lower(self, value):
        """
        Used to sort a value to lower case, depending of the type
        """
        if isinstance(value, str):
            return value.lower()
        else:
            return value

    """
    **********************************************************************
    * Sort by tests                                                      *
    **********************************************************************
    """

    def non_null_col(self, json_data, column):
        flag = True
        column_list = []
        if type(column) is list:
            column_list = column
        else:
            column_list.append(column)

        for col in column_list:
            for data in json_data:
                if col not in data['configuration']:
                    flag = False
                break
        return flag

    def port_sort_by_name(self, desc=False):
        print("\n########## Test to sort port by name##########\n")

        expected_values = []

        for i in range(1, NUM_FAKE_PORTS + 1):
            port_name = "Port-%s" % i
            expected_values.append(port_name)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "name", http.client.OK, desc)
        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        if self.non_null_col(json_data, "name"):
            self.check_sort_expectations(
                expected_values, json_data, "name")

        print("########## End Test to sort ports by name##########\n")

    def port_sort_by_interfaces(self, desc=False):
        print("\n########## Test to sort port by interfaces##########\n")

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            interfaces = []
            if not desc:
                interfaces = ["/rest/v1/system/interfaces/%s" %
                              (NUM_FAKE_PORTS + 1 - i)]
            else:
                interfaces = ["/rest/v1/system/interfaces/%s" % i]

            update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                              "interfaces", interfaces, cookie_header)
            expected_values.append(interfaces)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        json_data = self.execute_sort_by_request("interfaces",
                                                 http.client.OK, desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "interfaces"):
            self.check_sort_expectations(expected_values, json_data,
                                         "interfaces")

        print("########## End Test to sort ports by interfaces ##########\n")

    def skip_port_sort_by_trunks(self, desc=False):
        print("\n########## Test to sort port by trunks ##########\n")

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            trunks = []
            if not desc:
                trunks = [NUM_FAKE_PORTS + 1 - i]
            else:
                trunks = [i]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "trunks", trunks,
                cookie_header)
            expected_values.append(trunks)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "trunks", http.client.OK, desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "trunks"):
            self.check_sort_expectations(
                expected_values, json_data, "trunks")
        print("\n########## End to sort port by trunks ##########\n")

    def port_sort_by_ip4_address(self, desc=False):
        print("\n########## Test to sort port by ip4 address ##########\n")

        json_data = self.execute_sort_by_request("ip4_address",
                                                 http.client.OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = "192.168.0.%(index)s/24" % {"index": i}
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip4_address"):
            self.check_sort_expectations(expected_values, json_data,
                                         "ip4_address")

        print("########## End Test to sort ports by ip4 address ##########\n")

    def port_sort_by_ip4_address_secondary(self, desc=False):
        print("\n########## Test to sort port by ip4_address_secondary "
              "##########\n")

        json_data = self.execute_sort_by_request("ip4_address_secondary",
                                                 http.client.OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = "192.168.1.%(index)s/24" % {"index": i}
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip4_address_secondary"):
            self.check_sort_expectations(
                expected_values, json_data, "ip4_address_secondary")

        print("\n########## End Test to sort port by ip4_address_secondary "
              "##########\n")

    def port_sort_by_lacp(self, desc=False):
        print("\n########## Test to sort port by lacp ##########\n")

        expected_values = []
        values = ["active", "passive", "off"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "lacp", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "lacp", http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "lacp"):
            self.check_sort_expectations(
                expected_values, json_data, "lacp")

        print("\n########## End Test to sort port by lacp ##########\n")

    def port_sort_by_bond_mode(self, desc=False):
        print("\n########## Test to sort port by bond_mode ##########\n")

        expected_values = []
        values = ["l2-src-dst-hash", "l3-src-dst-hash"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "bond_mode", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("bond_mode",
                                                 http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "bond_mode"):
            self.check_sort_expectations(expected_values, json_data,
                                         "bond_mode")

        print("\n########## End Test to sort port by bond_mode ##########\n")

    def skip_port_sort_by_tag(self, desc=False):
        print("\n########## Test to sort port by tag ##########\n")

        expected_values = []
        values = fill_with_function(random.randint(1, 4094), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1)]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "tag", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "tag", http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "tag"):
            self.check_sort_expectations(
                expected_values, json_data, "tag")

        print("\n########## End Test to sort port by tag ##########\n")

    def port_sort_by_vlan_mode(self, desc=False):
        print("\n########## Test to sort port by vlan_mode ##########\n")

        expected_values = []
        values = ["trunk", "access", "native-tagged", "native-untagged"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "vlan_mode", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("vlan_mode",
                                                 http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "vlan_mode"):
            self.check_sort_expectations(expected_values, json_data,
                                         "vlan_mode")

        print("\n########## End Test to sort port by vlan_mode ##########\n")

    def port_sort_by_mac(self, desc=False):
        print("\n########## Test to sort port by mac ##########\n")

        expected_values = []
        values = fill_with_function(random_mac(), NUM_FAKE_PORTS)

        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "mac", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "mac", http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "mac"):
            self.check_sort_expectations(
                expected_values, json_data, "mac")

        print("\n########## End Test to sort port by mac ##########\n")

    def port_sort_by_bond_active_slave(self, desc=False):
        print("\n########## Test to sort port by bond_active_slave "
              "##########\n")

        expected_values = []
        values = fill_with_function(random_mac(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                              "bond_active_slave", value,
                              cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("bond_active_slave",
                                                 http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "bond_active_slave"):
            self.check_sort_expectations(
                expected_values, json_data, "bond_active_slave")

        print("\n########## End Test to sort port by bond_active_slave "
              "##########\n")

    def port_sort_by_ip6_address(self, desc=False):
        print("\n########## Test to sort port by ip6_address ##########\n")

        expected_values = []
        values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                              "ip6_address", value, cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("ip6_address",
                                                 http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip6_address"):
            self.check_sort_expectations(expected_values, json_data,
                                         "ip6_address")

        print("\n########## End Test to sort port by ip6_address ##########\n")

    def port_sort_by_ip6_address_secondary(self, desc=False):
        print("\n########## Test to sort port by ip6_address_secondary "
              "##########\n")

        expected_values = []
        values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                              "ip6_address_secondary", [value],
                              cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("ip6_address_secondary",
                                                 http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip6_address_secondary"):
            self.check_sort_expectations(
                expected_values, json_data, "ip6_address_secondary")

        print("\n########## End Test to sort port by ip6_address_secondary "
              "##########\n")

    def port_sort_by_admin(self, desc=False):
        print("\n########## Test to sort port by admin ##########\n")

        expected_values = []
        values = ["up", "down"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field(
                SWITCH_IP, PATH + "/Port-%s" % i, "admin", value,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "admin", http.client.OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "admin"):
            self.check_sort_expectations(
                expected_values, json_data, "admin")

        print("\n########## End Test to sort port by admin ##########\n")

    def port_sort_by_admin_name(self, desc=False):
        print("\n########## Test to sort port by (admin,name) ##########\n")

        expected_values = []
        admin_values = ["up", "down"]
        random.seed()
        for i in range(1, NUM_FAKE_PORTS + 1):
            port = "Port-%s" % i
            admin_value = admin_values[(i - 1) % len(admin_values)]
            update_test_field(
                SWITCH_IP, PATH + "/" + port, "admin", admin_value,
                cookie_header)
            expected_dict = {"admin": admin_value, "name": port}
            expected_values.append(expected_dict)

        columns = ["admin", "name"]

        compare_function = self.tuple_lambda(columns)
        expected_values = sorted(expected_values, key=compare_function,
                                 reverse=desc)

        json_data = self.execute_sort_by_request(
            columns, http.client.OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        for i in range(0, len(expected_values)):
            expected_name = expected_values[i]["name"]
            expected_admin = expected_values[i]["admin"]
            returned_name = json_data[i]["configuration"]["name"]
            returned_admin = json_data[i]["configuration"]["admin"]

            if self.non_null_col(json_data, columns):
                assert returned_name == expected_name and \
                    expected_admin == returned_admin, \
                    "Wrong order. Expected: %s Returned: %s" \
                    % (expected_name, returned_name)

        print("\n######## End Test to sort port by (admin,name) ########\n")

    def port_sort_by_invalid_column(self, desc=False):
        test_title = "Test to sort port by invalid column"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("invalid_column",
                                                 http.client.BAD_REQUEST, desc)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_without_depth_parameter(self, desc=False):
        test_title = "Test to sort port without depth parameter"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 http.client.BAD_REQUEST,
                                                 desc, depth=None)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_invalid_pagination_parameter(self, desc=False):
        test_title = "Test to sort port with invalid pagination parameter"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 http.client.BAD_REQUEST,
                                                 desc, offset="one")
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_offset_equals_zero(self, desc=False):
        test_title = "Test to sort port with offset equals zero"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 http.client.OK, desc,
                                                 offset=0)
        assert len(json_data) == NUM_FAKE_PORTS,\
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_equals_zero(self, desc=False):
        test_title = "Test to sort port with limit equals zero"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 http.client.BAD_REQUEST,
                                                 desc, limit=0)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_shows_last_result(self, desc=False):
        test_title = "Test to sort port shows last result"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", http.client.OK, desc,
                                         limit=2,
                                         offset=NUM_FAKE_PORTS - 1,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == 1, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_negative_limit(self, desc=False):
        test_title = "Test to sort port with negative limit"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 http.client.BAD_REQUEST,
                                                 desc, limit=-1)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_equals_all_elements_in_db(self, desc=False):
        """
        Test all available ports with the limit parameter equal to the same
        amount of filtered ports requested
        """
        test_title = "Test to sort port with limit == all elements in db"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", http.client.OK, desc,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == NUM_FAKE_PORTS, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_higher_all_elements_in_db(self, desc=False):
        """
        Test all available ports with the limit parameter higher to the amount
        of filtered ports requested
        """
        test_title = "Test to sort port with limit > all elements in db"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", http.client.OK, desc,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == NUM_FAKE_PORTS, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_all_available_keys(self, desc=False):
        """
        Test ports resource by sorting with all the available keys
        """
        test_title = "Test to sort port with all available keys"
        print("\n########## " + test_title + " ##########\n")

        expected_values = []
        admin_values = ["up", "down"]
        random.seed()
        for i in range(1, NUM_FAKE_PORTS + 1):
            port = "Port-%s" % i
            admin_value = admin_values[(i - 1) % len(admin_values)]
            update_test_field(
                SWITCH_IP, PATH + "/" + port, "admin", admin_value,
                cookie_header)
            status_code, response_data = execute_request(
                PATH + "/" + port, "GET", None, SWITCH_IP,
                xtra_header=cookie_header)
            assert status_code == http.client.OK, "Wrong status code %s " % \
                status_code
            if isinstance(response_data, bytes):
                response_data = response_data.decode("utf-8")
            json_data = json.loads(response_data)
            expected_dict = json_data['configuration']
            expected_values.append(expected_dict)

        columns = []
        for key in expected_values[0].keys():
            columns.append(key)

        compare_function = self.tuple_lambda(columns)
        expected_values = sorted(expected_values, key=compare_function,
                                 reverse=desc)

        json_data = self.execute_sort_by_request(
            columns, http.client.OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        if self.non_null_col(json_data, columns):
            for i in range(0, len(json_data)):
                for column in columns:
                    assert json_data[i]["configuration"][column] == \
                        expected_values[i][column], \
                        "Wrong order. Expected: %s Returned: %s" \
                        % (expected_values[i][column],
                           json_data[i]["configuration"][column])
        print("########## End " + test_title + " ##########\n")

    def tuple_lambda(self, columns):
        return lambda item: tuple(self.sort_value_to_lower(item[k])
                                  for k in columns)

    def run_tests(self):
        """
        This method will inspect itstep to retrieve all existing methodS.
        Only methods that begin with "test_" will be executed.
        """
        methodlist = [n for n, v in inspect.getmembers(
            self, inspect.ismethod) if isinstance(v, types.MethodType)]
        print("\n######## Start Port Sort Tests Ascending Order ########\n")
        for name in methodlist:
            if name.startswith("port_"):
                # Ascending Order Test
                getattr(self, "%s" % name)()
        print("\n########## End Port Sort Tests Ascending Order ##########\n")
        print("\n########## Start Port Sort Tests Descending Order "
              "##########\n")
        for name in methodlist:
            if name.startswith("port_"):
                # Descending Order Test
                getattr(self, "%s" % name)(desc=True)
        print("\n######### End Port Sort Tests Descending Order #########\n")


class QuerySortPortTestOstl():
    def __init__(self, hs1, step, login_result):
        self.hs1 = hs1
        self.step = step
        self.login_result = login_result

    def execute_sort_by_request(self, attributes, expected_code, desc=False,
                                limit=None, offset=None, depth=1,
                                filters=None):
        """
        Common function to send a sort request
        :param attributes
        :param expected_code
        :param desc
        :param limit:
        :param offset:
        :param depth:
        :param filters
        """
        path = PATH + "?"
        if depth is not None:
            path += "depth=" + str(depth) + ";"
        if limit is not None:
            path += "limit=" + str(limit) + ";"
        if offset is not None:
            path += "offset=" + str(offset) + ";"

        if filters is not None:
            if isinstance(filters, dict):
                for key in filters.keys():
                    path += key + "=" + filters[key]
                path += ";"
            else:
                path += filters[key] + ";"

        path += "sort="

        if desc:
            path += "-"
        if isinstance(attributes, list):
            for attr in attributes:
                path += attr
                if attr != attributes[-1]:
                    path += ","
            attributes = ','.join(attributes)
        else:
            path += attributes

        if desc:
            attributes = '-' + attributes
        print("### Request to %s ###\n" % path)
        print("attributes --> %s" % attributes)

        args = {'depth': depth, 'sort': attributes, 'https': CRT_DIRECTORY_HS,
                'cookies': self.login_result.get('cookies'),
                'request_timeout': 5}
        if offset is not None:
            args['offset'] = offset
        if limit is not None:
            args['limit'] = limit
        if filters is not None and isinstance(filters, dict):
            for k, v in filters.items():
                args[k] = v

        get_result = self.hs1.libs.openswitch_rest.system_ports_get(**args)

        status_code = get_result.get('status_code')
        response_data = get_result["content"]
        assert status_code == expected_code, "Wrong status code %s " % \
                                             status_code
        self.step("### Status code is %s ###\n" % status_code)
        assert response_data is not "", \
            "Response data received is malformed: %s\n" % response_data

        # In order to no affect the tests the bridge_normal is removed
        if expected_code == HTTP_OK:
            self.remove_bridge_from_data(response_data)
        return response_data

    def remove_bridge_from_data(self, json_data):
        """
        Function used to remove the bridge_normal from test data
        """
        index = None
        for i in range(0, len(json_data)):
            if json_data[i]["configuration"]["name"] == "bridge_normal":
                index = i
                break
        if index is not None:
            json_data.pop(index)

    def check_sort_expectations(self, expected_values, json_data, field):
        """
        Common function to check order expectations
        """
        for i in range(0, len(expected_values)):
            # Expected values
            expected_value = expected_values[i]
            # Returned values
            returned_value = json_data[i]["configuration"][field]
            if (isinstance(returned_value, list) and
                    not isinstance(expected_value, list)):
                expected_value = [expected_value]

            assert expected_value == returned_value, "Wrong order. \
                    Expected: %s Returned: %s" % (expected_value,
                                                  returned_value)

    def sort_value_to_lower(self, value):
        """
        Used to sort a value to lower case, depending of the type
        """
        if isinstance(value, str):
            return value.lower()
        else:
            return value

    """
    **********************************************************************
    * Sort by tests                                                      *
    **********************************************************************
    """

    def non_null_col(self, json_data, column):
        flag = True
        column_list = []
        if type(column) is list:
            column_list = column
        else:
            column_list.append(column)

        for col in column_list:
            for data in json_data:
                if col not in data['configuration']:
                    flag = False
                break
        return flag

    def port_sort_by_name(self, desc=False):
        print("\n########## Test to sort port by name##########\n")

        expected_values = []

        for i in range(1, NUM_FAKE_PORTS + 1):
            port_name = "Port-%s" % i
            expected_values.append(port_name)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "name", HTTP_OK, desc)
        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        if self.non_null_col(json_data, "name"):
            self.check_sort_expectations(
                expected_values, json_data, "name")

        print("########## End Test to sort ports by name##########\n")

    def port_sort_by_interfaces(self, desc=False):
        print("\n########## Test to sort port by interfaces##########\n")

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            interfaces = []
            if not desc:
                interfaces = ["/rest/v1/system/interfaces/%s" %
                              (NUM_FAKE_PORTS + 1 - i)]
            else:
                interfaces = ["/rest/v1/system/interfaces/%s" % i]

            update_test_field_ostl(SWITCH_IP, PATH + "/Port-%s" % i,
                                   "interfaces", interfaces, "Port-%s" % i,
                                   self.hs1, self.step, self.login_result,
                                   cookie_header)
            expected_values.append(interfaces)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        json_data = self.execute_sort_by_request("interfaces",
                                                 HTTP_OK, desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "interfaces"):
            self.check_sort_expectations(expected_values, json_data,
                                         "interfaces")

        print("########## End Test to sort ports by interfaces ##########\n")

    def skip_port_sort_by_trunks(self, desc=False):
        print("\n########## Test to sort port by trunks ##########\n")

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            trunks = []
            if not desc:
                trunks = [NUM_FAKE_PORTS + 1 - i]
            else:
                trunks = [i]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "trunks", trunks,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(trunks)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "trunks", HTTP_OK, desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "trunks"):
            self.check_sort_expectations(
                expected_values, json_data, "trunks")
        print("\n########## End to sort port by trunks ##########\n")

    def port_sort_by_ip4_address(self, desc=False):
        print("\n########## Test to sort port by ip4 address ##########\n")

        json_data = self.execute_sort_by_request("ip4_address",
                                                 HTTP_OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = "192.168.0.%(index)s/24" % {"index": i}
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip4_address"):
            self.check_sort_expectations(expected_values, json_data,
                                         "ip4_address")

        print("########## End Test to sort ports by ip4 address ##########\n")

    def port_sort_by_ip4_address_secondary(self, desc=False):
        print("\n########## Test to sort port by ip4_address_secondary "
              "##########\n")

        json_data = self.execute_sort_by_request("ip4_address_secondary",
                                                 HTTP_OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        expected_values = []
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = "192.168.1.%(index)s/24" % {"index": i}
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip4_address_secondary"):
            self.check_sort_expectations(
                expected_values, json_data, "ip4_address_secondary")

        print("\n########## End Test to sort port by ip4_address_secondary "
              "##########\n")

    def port_sort_by_lacp(self, desc=False):
        print("\n########## Test to sort port by lacp ##########\n")

        expected_values = []
        values = ["active", "passive", "off"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "lacp", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "lacp", HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "lacp"):
            self.check_sort_expectations(
                expected_values, json_data, "lacp")

        print("\n########## End Test to sort port by lacp ##########\n")

    def port_sort_by_bond_mode(self, desc=False):
        print("\n########## Test to sort port by bond_mode ##########\n")

        expected_values = []
        values = ["l2-src-dst-hash", "l3-src-dst-hash"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "bond_mode", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("bond_mode",
                                                 HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "bond_mode"):
            self.check_sort_expectations(expected_values, json_data,
                                         "bond_mode")

        print("\n########## End Test to sort port by bond_mode ##########\n")

    def skip_port_sort_by_tag(self, desc=False):
        print("\n########## Test to sort port by tag ##########\n")

        expected_values = []
        values = fill_with_function(random.randint(1, 4094), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "tag", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "tag", HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "tag"):
            self.check_sort_expectations(
                expected_values, json_data, "tag")

        print("\n########## End Test to sort port by tag ##########\n")

    def port_sort_by_vlan_mode(self, desc=False):
        print("\n########## Test to sort port by vlan_mode ##########\n")

        expected_values = []
        values = ["trunk", "access", "native-tagged", "native-untagged"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "vlan_mode", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("vlan_mode",
                                                 HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "vlan_mode"):
            self.check_sort_expectations(expected_values, json_data,
                                         "vlan_mode")

        print("\n########## End Test to sort port by vlan_mode ##########\n")

    def port_sort_by_mac(self, desc=False):
        print("\n########## Test to sort port by mac ##########\n")

        expected_values = []
        values = fill_with_function(random_mac(), NUM_FAKE_PORTS)

        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "mac", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request(
            "mac", HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "mac"):
            self.check_sort_expectations(
                expected_values, json_data, "mac")

        print("\n########## End Test to sort port by mac ##########\n")

    def port_sort_by_bond_active_slave(self, desc=False):
        print("\n########## Test to sort port by bond_active_slave "
              "##########\n")

        expected_values = []
        values = fill_with_function(random_mac(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field_ostl(SWITCH_IP, PATH + "/Port-%s" % i,
                                   "bond_active_slave", value,
                                   "Port-%s" % i, self.hs1, self.step,
                                   self.login_result, cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("bond_active_slave",
                                                 HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "bond_active_slave"):
            self.check_sort_expectations(
                expected_values, json_data, "bond_active_slave")

        print("\n########## End Test to sort port by bond_active_slave "
              "##########\n")

    def port_sort_by_ip6_address(self, desc=False):
        print("\n########## Test to sort port by ip6_address ##########\n")

        expected_values = []
        values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field_ostl(SWITCH_IP, PATH + "/Port-%s" % i,
                                   "ip6_address", value,
                                   "Port-%s" % i, self.hs1, self.step,
                                   self.login_result, cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("ip6_address",
                                                 HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip6_address"):
            self.check_sort_expectations(expected_values, json_data,
                                         "ip6_address")

        print("\n########## End Test to sort port by ip6_address ##########\n")

    def port_sort_by_ip6_address_secondary(self, desc=False):
        print("\n########## Test to sort port by ip6_address_secondary "
              "##########\n")

        expected_values = []
        values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[i - 1]
            update_test_field_ostl(SWITCH_IP, PATH + "/Port-%s" % i,
                                   "ip6_address_secondary", [value],
                                   "Port-%s" % i, self.hs1, self.step,
                                   self.login_result, cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        json_data = self.execute_sort_by_request("ip6_address_secondary",
                                                 HTTP_OK, desc)

        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        if self.non_null_col(json_data, "ip6_address_secondary"):
            self.check_sort_expectations(
                expected_values, json_data, "ip6_address_secondary")

        print("\n########## End Test to sort port by ip6_address_secondary "
              "##########\n")

    def port_sort_by_admin(self, desc=False):
        print("\n########## Test to sort port by admin ##########\n")

        expected_values = []
        values = ["up", "down"]
        for i in range(1, NUM_FAKE_PORTS + 1):
            value = values[(i - 1) % len(values)]
            print("updating port with value %s" % value)
            update_test_field_ostl(
                SWITCH_IP, PATH + "/Port-%s" % i, "admin", value,
                "Port-%s" % i, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_values.append(value)

        expected_values.sort(
            key=lambda val: self.sort_value_to_lower(val), reverse=desc)

        print("before execute sort by request")
        json_data = self.execute_sort_by_request(
            "admin", HTTP_OK, desc)

        print("after execute sort by request")
        assert len(json_data) is (NUM_FAKE_PORTS), \
            "Retrieved more expected ports!"

        # print("\nExpected values: %s" % expected_values)
        # for a in json_data:
        #     print("admin val %s" % a['configuration']['admin'])
        if self.non_null_col(json_data, "admin"):
            self.check_sort_expectations(
                expected_values, json_data, "admin")

        print("\n########## End Test to sort port by admin ##########\n")

    def port_sort_by_admin_name(self, desc=False):
        print("\n########## Test to sort port by (admin,name) ##########\n")

        expected_values = []
        admin_values = ["up", "down"]
        random.seed()
        for i in range(1, NUM_FAKE_PORTS + 1):
            port = "Port-%s" % i
            admin_value = admin_values[(i - 1) % len(admin_values)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/" + port, "admin", admin_value,
                port, self.hs1, self.step, self.login_result,
                cookie_header)
            expected_dict = {"admin": admin_value, "name": port}
            expected_values.append(expected_dict)

        columns = ["admin", "name"]

        compare_function = self.tuple_lambda(columns)
        expected_values = sorted(expected_values, key=compare_function,
                                 reverse=desc)

        json_data = self.execute_sort_by_request(
            columns, HTTP_OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        for i in range(0, len(expected_values)):
            expected_name = expected_values[i]["name"]
            expected_admin = expected_values[i]["admin"]
            returned_name = json_data[i]["configuration"]["name"]
            returned_admin = json_data[i]["configuration"]["admin"]

            if self.non_null_col(json_data, columns):
                assert returned_name == expected_name and \
                    expected_admin == returned_admin, \
                    "Wrong order. Expected: %s Returned: %s" \
                    % (expected_name, returned_name)

        print("\n######## End Test to sort port by (admin,name) ########\n")

    def port_sort_by_invalid_column(self, desc=False):
        test_title = "Test to sort port by invalid column"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("invalid_column",
                                                 HTTP_BAD_REQUEST, desc)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_without_depth_parameter(self, desc=False):
        test_title = "Test to sort port without depth parameter"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 HTTP_BAD_REQUEST,
                                                 desc, depth=None)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_invalid_pagination_parameter(self, desc=False):
        test_title = "Test to sort port with invalid pagination parameter"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 HTTP_BAD_REQUEST,
                                                 desc, offset="one")
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_offset_equals_zero(self, desc=False):
        test_title = "Test to sort port with offset equals zero"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 HTTP_OK, desc,
                                                 offset=0)
        assert len(json_data) == NUM_FAKE_PORTS,\
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_equals_zero(self, desc=False):
        test_title = "Test to sort port with limit equals zero"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 HTTP_BAD_REQUEST,
                                                 desc, limit=0)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_shows_last_result(self, desc=False):
        test_title = "Test to sort port shows last result"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", HTTP_OK, desc,
                                         limit=2,
                                         offset=NUM_FAKE_PORTS - 1,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == 1, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_negative_limit(self, desc=False):
        test_title = "Test to sort port with negative limit"
        print("\n########## " + test_title + " ##########\n")
        json_data = self.execute_sort_by_request("name",
                                                 HTTP_BAD_REQUEST,
                                                 desc, limit=-1)
        print("Request response: %s\n" % json_data)
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_equals_all_elements_in_db(self, desc=False):
        """
        Test all available ports with the limit parameter equal to the same
        amount of filtered ports requested
        """
        test_title = "Test to sort port with limit == all elements in db"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", HTTP_OK, desc,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == NUM_FAKE_PORTS, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_limit_higher_all_elements_in_db(self, desc=False):
        """
        Test all available ports with the limit parameter higher to the amount
        of filtered ports requested
        """
        test_title = "Test to sort port with limit > all elements in db"
        print("\n########## " + test_title + " ##########\n")
        filtered_ports = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            filtered_ports += "Port-%s," % i
        filtered_ports = filtered_ports.rstrip(",")
        json_data = \
            self.execute_sort_by_request("name", HTTP_OK, desc,
                                         filters={
                                             "name": filtered_ports})
        assert len(json_data) == NUM_FAKE_PORTS, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + test_title + " ##########\n")

    def port_sort_with_all_available_keys(self, desc=False):
        """
        Test ports resource by sorting with all the available keys
        """
        test_title = "Test to sort port with all available keys"
        print("\n########## " + test_title + " ##########\n")

        expected_values = []
        admin_values = ["up", "down"]
        random.seed()
        for i in range(1, NUM_FAKE_PORTS + 1):
            port = "Port-%s" % i
            admin_value = admin_values[(i - 1) % len(admin_values)]
            update_test_field_ostl(
                SWITCH_IP, PATH + "/" + port, "admin", admin_value, port,
                self.hs1, self.step, self.login_result,
                cookie_header)
            # status_code, response_data = execute_request(
            #     PATH + "/" + port, "GET", None, SWITCH_IP,
            #     xtra_header=cookie_header)

            get_result = self.hs1.libs.openswitch_rest.system_ports_id_get(
                port,
                https=CRT_DIRECTORY_HS,
                cookies=self.login_result.get('cookies'),
                request_timeout=5)

            status_code = get_result.get('status_code')
            response_data = get_result["content"]
            assert status_code == HTTP_OK, "Wrong status code %s " % \
                status_code
            self.step("### Status code is %s ###\n" % status_code)
            assert response_data is not "", \
                "Response data received is malformed: %s\n" % response_data
            assert status_code == HTTP_OK, "Wrong status code %s " % \
                status_code
            # if isinstance(response_data, bytes):
            #     response_data = response_data.decode("utf-8")
            # json_data = json.loads(response_data)
            json_data = response_data
            expected_dict = json_data['configuration']
            expected_values.append(expected_dict)

        columns = []
        for key in expected_values[0].keys():
            columns.append(key)

        compare_function = self.tuple_lambda(columns)
        expected_values = sorted(expected_values, key=compare_function,
                                 reverse=desc)

        json_data = self.execute_sort_by_request(
            columns, HTTP_OK, desc)

        assert len(json_data) is (
            NUM_FAKE_PORTS), "Retrieved more expected ports!"

        if self.non_null_col(json_data, columns):
            for i in range(0, len(json_data)):
                for column in columns:
                    assert json_data[i]["configuration"][column] == \
                        expected_values[i][column], \
                        "Wrong order. Expected: %s Returned: %s" \
                        % (expected_values[i][column],
                           json_data[i]["configuration"][column])
        print("########## End " + test_title + " ##########\n")

    def tuple_lambda(self, columns):
        return lambda item: tuple(self.sort_value_to_lower(item[k])
                                  for k in columns)

    def run_tests(self):
        """
        This method will inspect itstep to retrieve all existing methodS.
        Only methods that begin with "test_" will be executed.
        """
        methodlist = [n for n, v in inspect.getmembers(
            self, inspect.ismethod) if isinstance(v, types.MethodType)]
        print("\n######## Start Port Sort Tests Ascending Order ########\n")
        for name in methodlist:
            if name.startswith("port_"):
                # Ascending Order Test
                getattr(self, "%s" % name)()
        print("\n########## End Port Sort Tests Ascending Order ##########\n")
        print("\n########## Start Port Sort Tests Descending Order "
              "##########\n")
        for name in methodlist:
            if name.startswith("port_"):
                # Descending Order Test
                getattr(self, "%s" % name)(desc=True)
        print("\n######### End Port Sort Tests Descending Order #########\n")


@mark.gate
@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_ports_get_sort(topology, step, netop_login,
                                     setup_test):
    test_query_sort_port = QuerySortPortTest()
    test_query_sort_port.run_tests()


@mark.gate
@mark.platform_incompatible(['docker'])
def test_ops_restd_ft_ports_get_sort_ostl(topology, step):
    global PATH, PORT_PATH, RESOURCE_NAME

    sw1 = topology.get('sw1')
    hs1 = topology.get('hs1')

    assert sw1 is not None
    assert hs1 is not None

    sw1.send_command('systemctl restart restd', shell='bash')
    date = str(datetime.now())
    sw1.send_command('date --set="%s"' % date, shell='bash')

    add_ip_devices(sw1, hs1, step)
    ensure_connectivity(hs1, step)
    set_rest_server(hs1, step)
    create_certificate_and_copy_to_host(sw1, SW_IP, HS_IP, step=step)

    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/" + RESOURCE_NAME

    login_result = login_to_physical_switch(hs1, sw1, step)
    setup_switch_ports_ostl(NUM_FAKE_PORTS, hs1, step, login_result)
    test_query_sort_port = QuerySortPortTestOstl(hs1, step, login_result)
    test_query_sort_port.run_tests()
