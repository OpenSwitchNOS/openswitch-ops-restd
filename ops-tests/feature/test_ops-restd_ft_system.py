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

from pytest import fixture, mark
from time import sleep
from os import environ
import json
import http.client

from rest_utils_ft import execute_request, login, get_json, \
    get_switch_ip, rest_sanity_check, get_server_crt, remove_server_crt
from swagger_test_utility import swagger_model_verification
from rest_utils_physical_ft import CRT_DIRECTORY_HS, HTTP_OK, SW_IP, HS_IP
from rest_utils_physical_ft import set_rest_server, add_ip_devices, \
    ensure_connectivity, login_to_physical_switch
from topology_common.ops.configuration_plane.rest.rest \
    import create_certificate_and_copy_to_host
from datetime import datetime


TOPOLOGY = """
#               +-------+
# +-------+     |       |
# |  sw1  <----->  hsw1 |
# +-------+     |       |
#               +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=oobmhost name="Host 1"] hs1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- hs1:1
"""

response_global = ""
cookie_header = None
SWITCH_IP = None
proxy = None
PATH = "/rest/v1/system"
h1 = None
login_result = None


@fixture(scope="module")
def setup_module(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    sleep(2)
    get_server_crt(sw1)
    rest_sanity_check(SWITCH_IP)


@fixture()
def setup(request, topology):
    global sw1
    sw1 = topology.get("sw1")
    assert sw1 is not None
    global SWITCH_IP
    if SWITCH_IP is None:
        SWITCH_IP = get_switch_ip(sw1)
    proxy = environ["https_proxy"]
    environ["https_proxy"] = ""
    get_server_crt(sw1)
    global cookie_header
    if cookie_header is None:
        cookie_header = login(SWITCH_IP)

    def cleanup():
        global cookie_header
        environ["https_proxy"] = proxy
        remove_server_crt()
        cookie_header = None

    request.addfinalizer(cleanup)


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


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_call_system_get(setup, setup_module, topology, step):
    print("\n########## Executing GET request on %s ##########\n" % PATH)
    container_id = sw1.container_id
    # # Execute GET
    response, json_string = execute_request(PATH, "GET", None, SWITCH_IP,
                                            True, xtra_header=cookie_header)

    assert response.status == http.client.OK

    get_data = {}

    try:
        # A malformed json should throw an exception here
        get_data = get_json(json_string)
    except:
        assert False

    # # Check data was received
    assert get_data
    assert type(get_data) is dict
    assert len(get_data) > 0

    print("\n######## Finished executing GET request on %s #######\n" % PATH)

    print("container_id_test_get_id %s\n" % container_id)
    swagger_model_verification(container_id, "/system", "GET_ID",
                               response_global)


@mark.gate
@mark.platform_incompatible(['docker'])
def test_call_system_get_ostl(topology, step, setup_module_physical):

    get_result = h1.libs.openswitch_rest.system_get(
        https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)
    assert get_result.get('status_code') == HTTP_OK

    get_data = {}

    try:
        get_data = get_result
    except:
        assert False

    assert get_data
    assert type(get_data) is dict
    assert len(get_data) > 0

    step("\n######## Finished executing GET request on %s #######\n" % PATH)


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_call_system_options(setup, setup_module, topology, step):
    print("\n########## Executing OPTIONS request on %s ##########\n" % PATH)

    # # Execute OPTIONS
    response, json_string = execute_request(PATH, "OPTIONS", None, SWITCH_IP,
                                            True, xtra_header=cookie_header)

    assert response.status == http.client.OK

    # # Check expected options are correct
    # TODO change these to propper expected values after correct OPTIONS
    # is implemented
    expected_allow = ["DELETE", "GET", "OPTIONS", "POST", "PUT", "PATCH"]
    response_allow = response.getheader("allow").split(", ")

    assert expected_allow == response_allow

    print("\n###### Finished executing OPTIONS request on %s #####\n" % PATH)


# TODO Implement test_call_system_options when it will be added to the
# library.
@mark.gate
@mark.platform_incompatible(['docker'])
def test_call_system_options_ostl(topology, step, setup_module_physical):
    print("\n########## Executing OPTIONS request on %s ##########\n" % PATH)


@mark.gate
@mark.skipif(True, reason="Disabling because test is failing")
def test_call_system_put(setup, setup_module, topology, step):
    global response_global
    print("\n########## Executing PUT request on %s ##########\n" % PATH)

    # # Get initial data
    response, pre_put_json_string = execute_request(PATH, "GET", None,
                                                    SWITCH_IP, True,
                                                    xtra_header=cookie_header)

    assert response.status == http.client.OK

    try:
        # A malformed json should throw an exception here
        pre_put_get_data = get_json(pre_put_json_string)
    except:
        assert False

    # # Execute PUT request
    put_data = pre_put_get_data['configuration']

    # Modify config keys
    put_data['hostname'] = 'switch'

    dns_servers = ["8.8.8.8"]
    if 'dns_servers' in put_data:
        put_data['dns_servers'].extend(dns_servers)
    else:
        put_data['dns_servers'] = dns_servers

    put_data['asset_tag_number'] = "1"

    other_config = {
        'stats-update-interval': "5001",
        'min_internal_vlan': "1024",
        'internal_vlan_policy': 'ascending',
        'max_internal_vlan': "4094",
        'enable-statistics': "false"
    }
    if 'other_config' in put_data:
        put_data['other_config'].update(other_config)
    else:
        put_data['other_config'] = other_config

    put_data['external_ids'] = {"id1": "value1"}

    ecmp_config = {
        'hash_srcip_enabled': "false",
        'hash_srcport_enabled': "false",
        'hash_dstip_enabled': "false",
        'enabled': "false",
        'hash_dstport_enabled': "false"
    }
    if 'ecmp_config' in put_data:
        put_data['ecmp_config'].update(ecmp_config)
    else:
        put_data['ecmp_config'] = ecmp_config

    bufmon_config = {
        'collection_period': "5",
        'threshold_trigger_rate_limit': "60",
        'periodic_collection_enabled': "false",
        'counters_mode': 'current',
        'enabled': "false",
        'snapshot_on_threshold_trigger': "false",
        'threshold_trigger_collection_enabled': "false"
    }
    if 'bufmon_config' in put_data:
        put_data['bufmon_config'].update(bufmon_config)
    else:
        put_data['bufmon_config'] = bufmon_config

    logrotate_config = {
        'maxsize': "10",
        'period': 'daily',
        'target': ''
    }
    if 'logrotate_config' in put_data:
        put_data['logrotate_config'].update(logrotate_config)
    else:
        put_data['logrotate_config'] = logrotate_config

    response_global = {"configuration": put_data}
    response, json_string = execute_request(PATH, "PUT",
                                            json.dumps({'configuration':
                                                        put_data}),
                                            SWITCH_IP, True,
                                            xtra_header=cookie_header)

    assert response.status == http.client.OK

    # # Get post-PUT data
    response, post_put_json_string = execute_request(PATH, "GET", None,
                                                     SWITCH_IP, True,
                                                     xtra_header=cookie_header)

    assert response.status == http.client.OK

    post_put_get_data = {}

    try:
        # A malformed json should throw an exception here
        post_put_get_data = get_json(post_put_json_string)
    except:
        assert False

    # post-PUT data should be the same as pre-PUT data
    post_put_data = post_put_get_data['configuration']

    assert put_data == post_put_data

    # # Perform bad PUT request
    json_string = json.dumps({'configuration': put_data})
    json_string += ","

    response, json_string = execute_request(PATH, "PUT", json_string,
                                            SWITCH_IP, True,
                                            xtra_header=cookie_header)

    assert response.status == http.client.BAD_REQUEST
    print("\n######## Finished executing PUT request on %s ########\n" % PATH)


@mark.gate
@mark.platform_incompatible(['docker'])
def test_call_system_put_ostl(topology, step, setup_module_physical):
    global response_global
    print("\n########## Executing PUT request on %s ##########\n" % PATH)

    # # Get initial data
    get_result = h1.libs.openswitch_rest.system_get(
        https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)
    assert get_result.get('status_code') == HTTP_OK
    print(get_result)

    # # Execute PUT request
    put_data = get_result["content"]["configuration"]

    # Modify config keys
    put_data["hostname"] = "switch"

    dns_servers = ["8.8.8.8"]
    if "dns_servers" in put_data:
        put_data["dns_servers"].extend(dns_servers)
    else:
        put_data["dns_servers"] = dns_servers

    put_data["asset_tag_number"] = "1"

    other_config = {
        "stats-update-interval": "5001",
        "min_internal_vlan": "1024",
        "internal_vlan_policy": 'ascending',
        "max_internal_vlan": "4094",
        "enable-statistics": "false"
        }
    if "other_config" in put_data:
        put_data["other_config"].update(other_config)
    else:
        put_data["other_config"] = other_config

    put_data["external_ids"] = {"id1": "value1"}

    ecmp_config = {
        "hash_srcip_enabled": "false",
        "hash_srcport_enabled": "false",
        "hash_dstip_enabled": "false",
        "hash_dstport_enabled": "false"
        }
    if "ecmp_config" in put_data:
        put_data["ecmp_config"].update(ecmp_config)
    else:
        put_data["ecmp_config"] = ecmp_config

    bufmon_config = {
        "collection_period": "5",
        "threshold_trigger_rate_limit": "60",
        "periodic_collection_enabled": "false",
        "counters_mode": "current",
        "enabled": "false",
        "snapshot_on_threshold_trigger": "false",
        "threshold_trigger_collection_enabled": "false"
        }
    if "bufmon_config" in put_data:
        put_data["bufmon_config"].update(bufmon_config)
    else:
        put_data["bufmon_config"] = bufmon_config

    logrotate_config = {
        "maxsize": "10",
        "period": 'daily'
        }

    if "logrotate_config" in put_data:
        put_data["logrotate_config"].update(logrotate_config)
    else:
        put_data["logrotate_config"] = logrotate_config

    response_global = {"configuration": put_data}

    put_result = h1.libs.openswitch_rest.system_put(
        response_global, https=CRT_DIRECTORY_HS,
        cookies=login_result.get('cookies'),
        request_timeout=5)
    assert put_result.get('status_code') == HTTP_OK
