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

from pytest import fixture


import json
import http.client

from rest_utils import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    update_test_field, fill_with_function, random_mac, random_ip6_address,
    get_server_crt, remove_server_crt
)
from fakes import create_fake_port
import random

from os import environ
from time import sleep

# Topology definition. the topology contains two back to back switches
# having four links between them.


TOPOLOGY = """
# +-------+     +-------+
# |  ops1  <----->  hs1  |
# +-------+     +-------+

# Nodes
[type=openswitch name="Switch 1"] ops1
[type=oobmhost name="Host 1"] hs1

# Ports
[force_name=oobm] ops1:sp1

# Links
ops1:sp1 -- hs1:1
"""


SWITCH_IP = None
cookie_header = None
proxy = None
PATH = None
PORT_PATH = None


NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0
NUM_FAKE_PORTS = 10

switches = []


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy, PATH, PORT_PATH, PATH_INT
    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/Port-1"
    cookie_header = None
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
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
def sanity_check(topology):
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)
    setup_switch_ports(NUM_FAKE_PORTS)


def execute_sort_by_request(step, attributes, expected_code, desc=False,
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

    step("### Request to %s ###\n" % path)
    status_code, response_data = execute_request(
        path, "GET", None, SWITCH_IP, xtra_header=cookie_header)

    assert status_code == expected_code, "Wrong status code %s " % \
                                         status_code
    step("### Status code is %s ###\n" % status_code)
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
        remove_bridge_from_data(json_data)
    return json_data


def remove_bridge_from_data(json_data):
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


def check_sort_expectations(expected_values, json_data, field):
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


def sort_value_to_lower(value):
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


def non_null_col(json_data, column):
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


def port_sort_by_name(step, desc=False):
    step("\n########## Test to sort port by name##########\n")

    expected_values = []

    for i in range(1, NUM_FAKE_PORTS + 1):
        port_name = "Port-%s" % i
        expected_values.append(port_name)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "name", http.client.OK, desc)
    assert len(json_data) is (
        NUM_FAKE_PORTS), "Retrieved more expected ports!"

    if non_null_col(json_data, "name"):
        check_sort_expectations(expected_values, json_data, "name")

    step("########## End Test to sort ports by name##########\n")


def port_sort_by_interfaces(step, desc=False):
    step("\n########## Test to sort port by interfaces##########\n")

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

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)
    json_data = execute_sort_by_request(step, "interfaces", http.client.OK,
                                        desc)
    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "interfaces"):
        check_sort_expectations(expected_values, json_data,
                                "interfaces")

    step("########## End Test to sort ports by interfaces ##########\n")


def port_sort_by_trunks(step, desc=False):
    step("\n########## Test to sort port by trunks ##########\n")

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

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "trunks", http.client.OK, desc)
    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "trunks"):
        check_sort_expectations(expected_values, json_data, "trunks")
    step("\n########## End to sort port by trunks ##########\n")


def port_sort_by_ip4_address(step, desc=False):
    step("\n########## Test to sort port by ip4 address ##########\n")

    json_data = execute_sort_by_request(step, "ip4_address", http.client.OK,
                                        desc)

    assert len(json_data) is (
        NUM_FAKE_PORTS), "Retrieved more expected ports!"

    expected_values = []
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = "192.168.0.%(index)s" % {"index": i}
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)
    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "ip4_address"):
        check_sort_expectations(expected_values, json_data,
                                "ip4_address")

    step("########## End Test to sort ports by ip4 address ##########\n")


def port_sort_by_ip4_address_secondary(step, desc=False):
    step("\n########## Test to sort port by ip4_address_secondary "
         "##########\n")

    json_data = execute_sort_by_request(step, "ip4_address_secondary",
                                        http.client.OK, desc)

    assert len(json_data) is (
        NUM_FAKE_PORTS), "Retrieved more expected ports!"

    expected_values = []
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = "192.168.1.%(index)s" % {"index": i}
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)
    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "ip4_address_secondary"):
        check_sort_expectations(
            expected_values, json_data, "ip4_address_secondary")

    step("\n########## End Test to sort port by ip4_address_secondary "
         "##########\n")


def port_sort_by_lacp(step, desc=False):
    step("\n########## Test to sort port by lacp ##########\n")

    expected_values = []
    values = ["active", "passive", "off"]
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[(i - 1) % len(values)]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "lacp", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "lacp", http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "lacp"):
        check_sort_expectations(expected_values, json_data, "lacp")

    step("\n########## End Test to sort port by lacp ##########\n")


def port_sort_by_bond_mode(step, desc=False):
    step("\n########## Test to sort port by bond_mode ##########\n")

    expected_values = []
    values = ["l2-src-dst-hash", "l3-src-dst-hash"]
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[(i - 1) % len(values)]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "bond_mode", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "bond_mode", http.client.OK,
                                        desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "bond_mode"):
        check_sort_expectations(expected_values, json_data,
                                "bond_mode")

    step("\n########## End Test to sort port by bond_mode ##########\n")


def port_sort_by_tag(step, desc=False):
    step("\n########## Test to sort port by tag ##########\n")

    expected_values = []
    values = fill_with_function(random.randint(1, 4094), NUM_FAKE_PORTS)
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[(i - 1)]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "tag", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "tag", http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "tag"):
        check_sort_expectations(expected_values, json_data, "tag")

    step("\n########## End Test to sort port by tag ##########\n")


def port_sort_by_vlan_mode(step, desc=False):
    step("\n########## Test to sort port by vlan_mode ##########\n")

    expected_values = []
    values = ["trunk", "access", "native-tagged", "native-untagged"]
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[(i - 1) % len(values)]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "vlan_mode", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "vlan_mode", http.client.OK,
                                        desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "vlan_mode"):
        check_sort_expectations(expected_values, json_data,
                                "vlan_mode")

    step("\n########## End Test to sort port by vlan_mode ##########\n")


def port_sort_by_mac(step, desc=False):
    step("\n########## Test to sort port by mac ##########\n")

    expected_values = []
    values = fill_with_function(random_mac(), NUM_FAKE_PORTS)

    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[i - 1]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "mac", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "mac", http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "mac"):
        check_sort_expectations(expected_values, json_data, "mac")

    step("\n########## End Test to sort port by mac ##########\n")


def port_sort_by_bond_active_slave(step, desc=False):
    step("\n########## Test to sort port by bond_active_slave "
         "##########\n")

    expected_values = []
    values = fill_with_function(random_mac(), NUM_FAKE_PORTS)
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[i - 1]
        update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                          "bond_active_slave", value,
                          cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "bond_active_slave",
                                        http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "bond_active_slave"):
        check_sort_expectations(
            expected_values, json_data, "bond_active_slave")

    step("\n########## End Test to sort port by bond_active_slave "
         "##########\n")


def port_sort_by_ip6_address(step, desc=False):
    step("\n########## Test to sort port by ip6_address ##########\n")

    expected_values = []
    values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[i - 1]
        update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                          "ip6_address", value, cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "ip6_address", http.client.OK,
                                        desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "ip6_address"):
        check_sort_expectations(expected_values, json_data,
                                "ip6_address")

    step("\n########## End Test to sort port by ip6_address ##########\n")


def port_sort_by_ip6_address_secondary(step, desc=False):
    step("\n########## Test to sort port by ip6_address_secondary "
         "##########\n")

    expected_values = []
    values = fill_with_function(random_ip6_address(), NUM_FAKE_PORTS)
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[i - 1]
        update_test_field(SWITCH_IP, PATH + "/Port-%s" % i,
                          "ip6_address_secondary", [value],
                          cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "ip6_address_secondary",
                                        http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "ip6_address_secondary"):
        check_sort_expectations(
            expected_values, json_data, "ip6_address_secondary")

    step("\n########## End Test to sort port by ip6_address_secondary "
         "##########\n")


def port_sort_by_admin(step, desc=False):
    step("\n########## Test to sort port by admin ##########\n")

    expected_values = []
    values = ["up", "down"]
    for i in range(1, NUM_FAKE_PORTS + 1):
        value = values[(i - 1) % len(values)]
        update_test_field(
            SWITCH_IP, PATH + "/Port-%s" % i, "admin", value,
            cookie_header)
        expected_values.append(value)

    expected_values.sort(key=lambda val: sort_value_to_lower(val),
                         reverse=desc)

    json_data = execute_sort_by_request(step, "admin", http.client.OK, desc)

    assert len(json_data) is (NUM_FAKE_PORTS), \
        "Retrieved more expected ports!"

    if non_null_col(json_data, "admin"):
        check_sort_expectations(expected_values, json_data, "admin")

    step("\n########## End Test to sort port by admin ##########\n")


def port_sort_by_admin_name(step, desc=False):
    step("\n########## Test to sort port by (admin,name) ##########\n")

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

    compare_function = tuple_lambda(columns)
    expected_values = sorted(expected_values, key=compare_function,
                             reverse=desc)

    json_data = execute_sort_by_request(step, columns, http.client.OK, desc)

    assert len(json_data) is (
        NUM_FAKE_PORTS), "Retrieved more expected ports!"

    for i in range(0, len(expected_values)):
        expected_name = expected_values[i]["name"]
        expected_admin = expected_values[i]["admin"]
        returned_name = json_data[i]["configuration"]["name"]
        returned_admin = json_data[i]["configuration"]["admin"]

        if non_null_col(json_data, columns):
            assert returned_name == expected_name and \
                expected_admin == returned_admin, \
                "Wrong order. Expected: %s Returned: %s" \
                % (expected_name, returned_name)

    step("\n########## End Test to sort port by (admin,name) ##########\n")


def port_sort_by_invalid_column(step, desc=False):
    test_title = "Test to sort port by invalid column"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "invalid_column",
                                        http.client.BAD_REQUEST, desc)
    step("Request response: %s\n" % json_data)
    step("########## End " + test_title + " ##########\n")


def port_sort_without_depth_parameter(step, desc=False):
    test_title = "Test to sort port without depth parameter"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "name", http.client.BAD_REQUEST,
                                        desc, depth=None)
    step("Request response: %s\n" % json_data)
    step("########## End " + test_title + " ##########\n")


def port_sort_with_invalid_pagination_parameter(step, desc=False):
    test_title = "Test to sort port with invalid pagination parameter"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "name", http.client.BAD_REQUEST,
                                        desc, offset="one")
    step("Request response: %s\n" % json_data)
    step("########## End " + test_title + " ##########\n")


def port_sort_with_offset_equals_zero(step, desc=False):
    test_title = "Test to sort port with offset equals zero"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "name", http.client.OK, desc,
                                        offset=0)
    assert len(json_data) == NUM_FAKE_PORTS,\
        "Retrieved a different amount of ports than expected!"
    step("########## End " + test_title + " ##########\n")


def port_sort_with_limit_equals_zero(step, desc=False):
    test_title = "Test to sort port with limit equals zero"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "name", http.client.BAD_REQUEST,
                                        desc, limit=0)
    step("Request response: %s\n" % json_data)
    step("########## End " + test_title + " ##########\n")


def port_sort_shows_last_result(step, desc=False):
    test_title = "Test to sort port shows last result"
    step("\n########## " + test_title + " ##########\n")
    filtered_ports = ""
    for i in range(1, NUM_FAKE_PORTS + 1):
        filtered_ports += "Port-%s," % i
    filtered_ports = filtered_ports.rstrip(",")
    json_data = \
        execute_sort_by_request(step, "name", http.client.OK, desc,
                                limit=2,
                                offset=NUM_FAKE_PORTS - 1,
                                filters={
                                    "name": filtered_ports})
    assert len(json_data) == 1, \
        "Retrieved a different amount of ports than expected!"
    step("########## End " + test_title + " ##########\n")


def port_sort_with_negative_limit(step, desc=False):
    test_title = "Test to sort port with negative limit"
    step("\n########## " + test_title + " ##########\n")
    json_data = execute_sort_by_request(step, "name", http.client.BAD_REQUEST,
                                        desc, limit=-1)
    step("Request response: %s\n" % json_data)
    step("########## End " + test_title + " ##########\n")


def port_sort_with_limit_equals_all_elements_in_db(step, desc=False):
    """
    Test all available ports with the limit parameter equal to the same
    amount of filtered ports requested
    """
    test_title = "Test to sort port with limit == all elements in db"
    step("\n########## " + test_title + " ##########\n")
    filtered_ports = ""
    for i in range(1, NUM_FAKE_PORTS + 1):
        filtered_ports += "Port-%s," % i
    filtered_ports = filtered_ports.rstrip(",")
    json_data = \
        execute_sort_by_request(step, "name", http.client.OK, desc,
                                filters={
                                    "name": filtered_ports})
    assert len(json_data) == NUM_FAKE_PORTS, \
        "Retrieved a different amount of ports than expected!"
    step("########## End " + test_title + " ##########\n")


def port_sort_with_limit_higher_all_elements_in_db(step, desc=False):
    """
    Test all available ports with the limit parameter higher to the amount
    of filtered ports requested
    """
    test_title = "Test to sort port with limit > all elements in db"
    step("\n########## " + test_title + " ##########\n")
    filtered_ports = ""
    for i in range(1, NUM_FAKE_PORTS + 1):
        filtered_ports += "Port-%s," % i
    filtered_ports = filtered_ports.rstrip(",")
    json_data = \
        execute_sort_by_request(step, "name", http.client.OK, desc,
                                filters={
                                    "name": filtered_ports})
    assert len(json_data) == NUM_FAKE_PORTS, \
        "Retrieved a different amount of ports than expected!"
    step("########## End " + test_title + " ##########\n")


def port_sort_with_all_available_keys(step, desc=False):
    """
    Test ports resource by sorting with all the available keys
    """
    test_title = "Test to sort port with all available keys"
    step("\n########## " + test_title + " ##########\n")

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

    compare_function = tuple_lambda(columns)
    expected_values = sorted(expected_values, key=compare_function,
                             reverse=desc)

    json_data = execute_sort_by_request(step, columns, http.client.OK, desc)

    assert len(json_data) is (
        NUM_FAKE_PORTS), "Retrieved more expected ports!"

    if non_null_col(json_data, columns):
        for i in range(0, len(json_data)):
            for column in columns:
                assert json_data[i]["configuration"][column] == \
                    expected_values[i][column], \
                    "Wrong order. Expected: %s Returned: %s" \
                    % (expected_values[i][column],
                       json_data[i]["configuration"][column])
    step("########## End " + test_title + " ##########\n")


def tuple_lambda(columns):
    return lambda item: tuple(sort_value_to_lower(item[k])
                              for k in columns)


def setup_switch_ports(total):
    for i in range(0, total):
        create_fake_port(PATH, SWITCH_IP, (i + 1))


def run_tests(step):
    """
    This method will inspect itstep to retrieve all existing methodS.
    Only methods that begin with "test_" will be executed.
    """
    step("\n########## Start Port Sort Tests Ascending Order ##########\n")
    port_sort_by_name(step)
    port_sort_by_interfaces(step)
    port_sort_by_trunks(step)
    port_sort_by_ip4_address(step)
    port_sort_by_ip4_address_secondary(step)
    port_sort_by_lacp(step)
    port_sort_by_bond_mode(step)
    port_sort_by_tag(step)
    port_sort_by_vlan_mode(step)
    port_sort_by_mac(step)
    port_sort_by_bond_active_slave(step)
    port_sort_by_ip6_address(step)
    port_sort_by_ip6_address_secondary(step)
    port_sort_by_admin(step)
    port_sort_by_admin_name(step)
    port_sort_by_invalid_column(step)
    port_sort_without_depth_parameter(step)
    port_sort_with_invalid_pagination_parameter(step)
    port_sort_with_offset_equals_zero(step)
    port_sort_with_limit_equals_zero(step)
    port_sort_shows_last_result(step)
    port_sort_with_negative_limit(step)
    port_sort_with_limit_equals_all_elements_in_db(step)
    port_sort_with_limit_higher_all_elements_in_db(step)
    port_sort_with_all_available_keys(step)
    step("\n########## End Port Sort Tests Ascending Order ##########\n")
    step("\n########## Start Port Sort Tests Descending Order "
         "##########\n")
    port_sort_by_name(step, desc=True)
    port_sort_by_interfaces(step, desc=True)
    port_sort_by_trunks(step, desc=True)
    port_sort_by_ip4_address(step, desc=True)
    port_sort_by_ip4_address_secondary(step, desc=True)
    port_sort_by_lacp(step, desc=True)
    port_sort_by_bond_mode(step, desc=True)
    port_sort_by_tag(step, desc=True)
    port_sort_by_vlan_mode(step, desc=True)
    port_sort_by_mac(step, desc=True)
    port_sort_by_bond_active_slave(step, desc=True)
    port_sort_by_ip6_address(step, desc=True)
    port_sort_by_ip6_address_secondary(step, desc=True)
    port_sort_by_admin(step, desc=True)
    port_sort_by_admin_name(step, desc=True)
    port_sort_by_invalid_column(step, desc=True)
    port_sort_without_depth_parameter(step, desc=True)
    port_sort_with_invalid_pagination_parameter(step, desc=True)
    port_sort_with_offset_equals_zero(step, desc=True)
    port_sort_with_limit_equals_zero(step, desc=True)
    port_sort_shows_last_result(step, desc=True)
    port_sort_with_negative_limit(step, desc=True)
    port_sort_with_limit_equals_all_elements_in_db(step, desc=True)
    port_sort_with_limit_higher_all_elements_in_db(step, desc=True)
    port_sort_with_all_available_keys(step, desc=True)
    step("\n########## End Port Sort Tests Descending Order ##########\n")


def test_ops_restd_ft_ports_get_sort(topology, step, netop_login,
                                     sanity_check):
    run_tests(step)
