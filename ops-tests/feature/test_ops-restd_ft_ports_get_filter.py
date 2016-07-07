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


import json
import http.client

from rest_utils_ft import (
    execute_request, login, get_switch_ip, rest_sanity_check,
    get_server_crt, remove_server_crt, update_test_field
)
from fakes import create_fake_port

from os import environ
from time import sleep

import inspect
import types

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

PATH = None


@fixture()
def netop_login(request, topology):
    global cookie_header, SWITCH_IP, proxy
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
def setup_test(topology):
    global PATH, PORT_PATH
    PATH = "/rest/v1/system/ports"
    PORT_PATH = PATH + "/Port1"
    ops1 = topology.get("ops1")
    assert ops1 is not None
    switches = [ops1]
    sleep(2)
    get_server_crt(switches[0])
    rest_sanity_check(SWITCH_IP)
    setup_switch_ports(NUM_FAKE_PORTS)


def setup_switch_ports(total):
    for i in range(1, total + 1):
        create_fake_port(PATH, SWITCH_IP, i)


class QueryFilterPortTest():

    def port_filter_by_name(self):
        global PATH
        field = "name"

        print("\n########## Test Filter name  ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            port = "Port-%s" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, port)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) == 1, "Retrieved a different " \
                                               "amount of ports than expected!"
            assert request_response[0]["configuration"][field] is not \
                port, "Retrieved different port!"

        print("########## End Test Filter name ##########\n")

    def port_filter_by_name_with_invalid_criteria(self):
        global PATH
        title = "Test Filter name  with invalid criteria"
        print("\n########## " + title + " ##########\n")
        field = "name"
        port = "invalid_criteria"
        path = "%s?selector=configuration&depth=1;%s=%s" % (PATH,
                                                            field,
                                                            port)
        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")
        assert len(request_response) == 0, "Expected No Results"
        print("########## End " + title + " ##########\n")

    def port_with_invalid_filter_and_invalid_criteria(self):
        global PATH
        title = "Test invalid filter name  with invalid criteria"
        print("\n########## " + title + " ##########\n")
        field = "invalid_filter"
        port = "invalid_criteria"
        path = "%s?selector=configuration&depth=1;%s=%s" % (PATH,
                                                            field,
                                                            port)
        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.BAD_REQUEST,
                                                 "")
        print("Request response: %s\n" % request_response)
        print("########## End " + title + " ##########\n")

    def port_with_valid_filters_and_valid_criteria(self):
        global PATH
        title = "Test valid filters name, mac and valid criteria"
        print("\n########## " + title + " ##########\n")
        fields = ["name", "mac"]
        criteria = ["Port-1", "01:23:45:67:89:01"]
        path = "%s?selector=configuration&depth=1;%s=%s;%s=%s" % \
               (PATH, fields[0], criteria[0],
                fields[1], criteria[1])
        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")
        for i in range(len(fields)):
            assert request_response[0]["configuration"][fields[i]] == \
                criteria[i], "Retrieved wrong port!"
        assert len(request_response) == 1, \
            "Retrieved more ports than expected!"
        print("########## End " + title + " ##########\n")

    def port_filter_without_depth_parameter(self):
        global PATH
        title = "Test Filter name without depth parameter"
        print("\n########## " + title + " ##########\n")
        field = "name"
        port = "Port-1"
        path = "%s?selector=configuration;%s=%s" % (PATH,
                                                    field,
                                                    port)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.BAD_REQUEST,
                                                 "")
        print("Request response: %s\n" % request_response)
        print("########## End " + title + " ##########\n")

    def port_with_complex_filter_mac(self):
        global PATH
        title = "Test complex filter mac and valid criteria"
        print("\n########## " + title + " ##########\n")
        field = "mac"
        mac = ""
        for i in range(1, NUM_FAKE_PORTS + 1):
            mac += "01:23:45:67:89:%02x," % i
        path = "%s?selector=configuration&depth=1;%s=%s" % (PATH,
                                                            field,
                                                            mac)
        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")
        assert len(request_response) == NUM_FAKE_PORTS, \
            "Retrieved a different amount of ports than expected!"
        print("########## End " + title + " ##########\n")

    def port_filter_by_interfaces(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3"]
        field = "interfaces"
        old_value = ["/rest/v1/system/interfaces/1"]
        new_value = ["/rest/v1/system/interfaces/3"]

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter interface  ##########\n")

        #######################################################################
        # Update port values
        ######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated port
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value[0])

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for port in range(0, updated_ports):
            assert request_response[port]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value[0])

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for port in range(0, other_ports):
            assert request_response[port]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Test Filter interface ##########\n")

    def port_filter_by_trunks(self):
        global PATH
        ports = ["Port-1", "Port-3", "Port-5"]
        field = "trunks"
        old_value = [413]
        new_value = [414]

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter trunk  ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated port
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value[0])

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for port in range(0, updated_ports):
            assert request_response[port]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value[0])

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for port in range(0, other_ports):
            assert request_response[port]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Filter Trunks ##########\n")

    def port_filter_by_primary_ip4_address(self):
        global PATH
        field = "ip4_address"

        print("\n########## Test Filter Primary IPv4 Address ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            ipv4 = "192.168.0.%s" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, ipv4)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) is 1, \
                "Retrieved more expected ports!"
            assert request_response[0]["configuration"][field] \
                is not ipv4, "Retrieved wrong port!"

        print("########## End Test Filter Primary IPv4 Address ##########\n")

    def port_filter_by_secondary_ipv4_address(self):
        global PATH
        field = "ip4_address_secondary"

        print("\n########## Test Filter Secondary IP4 Address  ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            ipv4 = "192.168.1.%s" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, ipv4)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) is 1, "Retrieved more expected ports!"
            assert request_response[0]["configuration"][field] is not \
                ipv4, "Retrieved wrong port!"

        print("########## End Test Filter Secondary IP4 Address ##########\n")

    def port_filter_by_lacp(self):
        global PATH
        field = "lacp"

        updated_ports = 2
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter Lacp ##########\n")

        ######################################################################
        # Update values
        ######################################################################
        update_test_field(SWITCH_IP,
                          PATH + "/Port-1",
                          field,
                          ["passive"],
                          cookie_header)

        update_test_field(SWITCH_IP,
                          PATH + "/Port-2",
                          field,
                          ["off"],
                          cookie_header)

        ######################################################################
        # Query for the updated ports
        ######################################################################
        path = PATH + "?depth=1;lacp=passive;lacp=off"

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, updated_ports):
            lacp_value = request_response[i]["configuration"][field]

            if lacp_value is "passive" or lacp_value is "off":
                assert False, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = PATH + "?depth=1;lacp=active"

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                "active", "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        update_test_field(SWITCH_IP,
                          PATH + "/Port-2",
                          field,
                          ["active"],
                          cookie_header)

        update_test_field(SWITCH_IP,
                          PATH + "/Port-3",
                          field,
                          ["active"],
                          cookie_header)

        print("########## End Test Filter Lacp ##########\n")

    def port_filter_by_bond_mode(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3"]
        field = "bond_mode"
        old_value = "l2-src-dst-hash"
        new_value = "l3-src-dst-hash"

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter bond_mode ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, updated_ports):
            assert request_response[i]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Filter bond_mode ##########\n")

    def port_filter_by_bond_active_slave(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3", "Port-4", "Port-5"]
        field = "bond_active_slave"
        old_value = "null"
        new_value = "00:98:76:54:32:10"

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter Bond Active Slave ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated port
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, updated_ports):
            assert request_response[i]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Test Filter Bond Active Slave ##########\n")

    def port_filter_by_tag(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3", "Port-4", "Port-5"]
        field = "tag"
        old_value = 654
        new_value = 123

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter Tag ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated port
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, updated_ports):
            assert request_response[i]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Test Filter Tag ##########\n")

    def port_filter_by_vlan_mode(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3"]
        field = "vlan_mode"
        old_value = "trunk"
        new_value = ["access", "native-tagged", "native-untagged"]

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter vlan_mode ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for i in range(0, updated_ports):
            update_test_field(SWITCH_IP,
                              PATH + "/" + ports[i],
                              field,
                              new_value[i],
                              cookie_header)

        #######################################################################
        # Query for the updated ports
        #######################################################################
        for mode in new_value:
            path = "%s?depth=1;%s=%s" % (PATH, field, mode)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) == 1, \
                "Retrieved more ports than expected!"

            assert request_response[0]["configuration"][field] == \
                mode, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Test Filter vlan_mode ##########\n")

    def port_filter_by_mac(self):
        global PATH
        field = "mac"

        print("\n########## Test Filter MAC ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            mac = "01:23:45:67:89:%02x" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, mac)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) is 1, \
                "Retrieved more expected ports!"

            assert request_response[0]["configuration"][field] is not \
                mac, "Retrieved wrong port!"

        print("########## End Test Filter MAC ##########\n")

    def port_filter_by_ipv6_address(self):
        global PATH
        field = "ip6_address"

        print("\n########## Test Filter Primary IPv6 Address ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            ip6 = "2001:0db8:85a3:0000:0000:8a2e:0370:%04d" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, ip6)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) is 1, \
                "Retrieved more expected ports!"

            assert request_response[0]["configuration"][field] is not \
                ip6, "Retrieved wrong port!"

        print("########## End Test Filter Primary IPv6 Address ##########\n")

    def port_filter_by_ipv6_address_secondary(self):
        global PATH
        field = "ip6_address_secondary"

        print("\n########## Test Filter Sec. IPv6 Address ##########\n")

        for i in range(1, NUM_FAKE_PORTS + 1):
            secondary_ip6 = "2001:0db8:85a3:0000:0000:8a2e:0371:%04d" % i
            path = "%s?depth=1;%s=%s" % (PATH, field, secondary_ip6)

            request_response = self.validate_request(SWITCH_IP,
                                                     path,
                                                     None,
                                                     "GET",
                                                     http.client.OK,
                                                     "")

            assert len(request_response) is 1, \
                "Retrieved more expected ports!"

            assert request_response[0]["configuration"][field] is not \
                secondary_ip6, "Retrieved wrong port!"

        print("########## End Test Filter Sec. IPv6 Address ##########\n")

    def port_filter_by_admin(self):
        global PATH
        ports = ["Port-1", "Port-2", "Port-3", "Port-4", "Port-5"]
        field = "admin"
        old_value = "up"
        new_value = "down"

        updated_ports = len(ports)
        other_ports = NUM_FAKE_PORTS - updated_ports

        print("\n########## Test Filter Admin ##########\n")

        #######################################################################
        # Update values
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              new_value,
                              cookie_header)

        #######################################################################
        # Query for the updated ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, new_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == updated_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, updated_ports):
            assert request_response[i]["configuration"][field] == \
                new_value, "Retrieved wrong port!"

        #######################################################################
        # Query for other ports
        #######################################################################
        path = "%s?depth=1;%s=%s" % (PATH, field, old_value)

        request_response = self.validate_request(SWITCH_IP,
                                                 path,
                                                 None,
                                                 "GET",
                                                 http.client.OK,
                                                 "")

        assert len(request_response) == other_ports, \
            "Retrieved more ports than expected!"

        for i in range(0, other_ports):
            assert request_response[i]["configuration"][field] == \
                old_value, "Retrieved wrong port!"

        #######################################################################
        # Restore default value
        #######################################################################
        for port in ports:
            update_test_field(SWITCH_IP,
                              PATH + "/" + port,
                              field,
                              old_value,
                              cookie_header)

        print("########## End Test Filter Admin ##########\n")

    def validate_request(self, switch_ip, path, data, op, expected_code,
                         expected_data):
        cookie_header = login(switch_ip)
        status_code, response_data = execute_request(path, op, data, switch_ip,
                                                     xtra_header=cookie_header)

        assert status_code == expected_code, \
            "Wrong status code %s " % status_code
        # print("### Status code is OK ###\n")

        assert response_data is not expected_data, \
            "Response data received: %s\n" % response_data
        # print("### Response data received: %s ###\n" % response_data)

        try:
            if isinstance(response_data, bytes):
                response_data = response_data.decode("utf-8")
            json_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"

        return json_data

    def run_tests(self):
        """
        This method will inspect itstep to retrieve all existing methods.

        Only methods that begin with "" will be executed.
        """
        methodlist = [n for n, v in inspect.getmembers(self, inspect.ismethod)
                      if isinstance(v, types.MethodType)]
        print("\n########## Starting Port Filter Tests ##########\n")
        for name in methodlist:
            if name.startswith("port_"):
                getattr(self, "%s" % name)()
        print("\n########## Ending Port Filter Tests ##########\n")


@mark.platform_incompatible(['ostl'])
def test_ops_restd_ft_ports_get_filter(topology, step, netop_login,
                                       setup_test):
    ops1 = topology.get("ops1")
    assert ops1 is not None

    test_query_filter_port = QueryFilterPortTest()
    test_query_filter_port.run_tests()
