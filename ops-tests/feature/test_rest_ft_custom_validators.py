# (C) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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

from pytest import mark

from rest_utils_ft import execute_request, get_switch_ip, \
    get_json, rest_sanity_check, login, get_server_crt, \
    remove_server_crt
import json
import http.client

TOPOLOGY = """
#               +-------+
# +-------+     |       |
# |  sw1  <----->  hsw1 |
# +-------+     |       |
#               +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=oobmhost name="Host 1"] h1

# Ports
[force_name=oobm] sw1:sp1

# Links
sw1:sp1 -- h1:if01
"""

BGP1_POST_DATA = {
    "configuration": {
        "always_compare_med": True,
        "asn": 6001
    }
}

BGP2_POST_DATA = {
    "configuration": {
        "always_compare_med": True,
        "asn": 6002
    }
}

DC_PUT_DATA = {
    "Interface": {
        "49": {
            "name": "49",
            "type": "system"
        }
    },
    "Port": {
        "p1": {
            "admin": ["up"],
            "name": "p1",
            "vlan_mode": ["trunk"],
            "trunks": [1]
        }
    },
    "System": {
        "aaa": {
            "fallback": "false",
            "radius": "false"
        },
        "asset_tag_number": "",
        "bridges": {
            "bridge_normal": {
                "datapath_type": "",
                "name": "bridge_normal",
                "ports": [
                    "p1"
                ]
            }
        },
        "hostname": "ops",
        "vrfs": {
            "vrf_default": {
                "name": "vrf_default"
            }
        }
    }
}

DC_INVALID_BGP_CONFIGS = {
    "bgp_routers": {
        "6001": {
            "always_compare_med": True
        },
        "6002": {
            "always_compare_med": True
        }
    },
    "name": "vrf_default"
}
cookie_header = None
SWITCH_IP = ""
post_url = "/rest/v1/system/vrfs/vrf_default/bgp_routers"
delete_url = post_url + "/6001"
dc_put_url = "/rest/v1/system/full-configuration?type=running"
dc_disable = pytest.mark.skipif(True, reason="new DC module does \
                                not have this feature.")


def netop_login():
    global cookie_header
    cookie_header = login(SWITCH_IP)


def custom_validator_valid_post():
    print("### Testing valid POST request ###\n")
    print("### Creating the first BGP should be successful ###\n")

    status_code, response_data = execute_request(post_url, "POST",
                                                 json.dumps(BGP1_POST_DATA),
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)
    assert status_code == http.client.CREATED

    status_code, response_data = execute_request(post_url, "GET", None,
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)
    assert status_code == http.client.OK
    assert post_url + '/6001' in str(response_data)

    print("### Successfully executed POST for url=%s ###\n" % post_url)
    print("### Received successful HTTP status code ###\n")


def custom_validator_invalid_post():
    print("### Testing invalid POST request ###\n")
    print("### Creating another BGP is not allowed ###\n")

    status_code, response_data = execute_request(post_url, "POST",
                                                 json.dumps(BGP2_POST_DATA),
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST

    assert 'exceeded' in str(response_data)

    d = get_json(response_data)
    print(d['message']['details'] + "\n")
    print("### Successfully retrieved validation error message ###\n")


def delete_bgp_router():
    print("### Cleanup by deleting BGP router ###\n")

    status_code, response_data = execute_request(delete_url, "DELETE", None,
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.NO_CONTENT
    print("### Successfully executed DELETE for url=%s ###\n" % delete_url)

    status_code, response_data = execute_request(delete_url, "GET", None,
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)
    assert status_code == http.client.NOT_FOUND

    print("### Received successful HTTP status code ###\n")


@dc_disable
def dc_test_custom_validator_valid_put():
    print("### Testing valid DC PUT request ###\n")

    status_code, response_data = execute_request(dc_put_url, "PUT",
                                                 json.dumps(DC_PUT_DATA),
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.OK
    print("### Successfully executed PUT for url=%s ###\n" % dc_put_url)

    status_code, response_data = execute_request(dc_put_url, "GET", None,
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)
    assert status_code == http.client.OK
    d = get_json(response_data)
    assert d['Interface']['49'] == DC_PUT_DATA['Interface']['49']
    assert d['Port']['p1'] == DC_PUT_DATA['Port']['p1']
    assert d['System']['aaa'] == DC_PUT_DATA['System']['aaa']

    print("### Received successful HTTP status code ###\n")


@dc_disable
def dc_test_custom_validator_invalid_put():
    print("### Testing invalid PUT request ###\n")
    print("### Adding invalid number of BGP routers ###\n")
    DC_PUT_DATA["System"]["vrfs"]["vrf_default"] = DC_INVALID_BGP_CONFIGS

    status_code, response_data = execute_request(dc_put_url, "PUT",
                                                 json.dumps(DC_PUT_DATA),
                                                 SWITCH_IP, False,
                                                 xtra_header=cookie_header)

    assert status_code == http.client.BAD_REQUEST

    assert 'exceeded' in response_data
    print("### Successfully executed PUT for url=%s ###\n" % dc_put_url)

    print("### Received expected non-successful HTTP status code ###\n")
    d = get_json(response_data)
    print(d['error'][1]['details'] + "\n")
    print("### Successfully retrieved validation error message ###\n")


@mark.gate
def test_custom_validators(topology):
    sw1 = topology.get('sw1')

    assert sw1 is not None
    global SWITCH_IP

    SWITCH_IP = get_switch_ip(sw1)

    get_server_crt(sw1)
    rest_sanity_check(SWITCH_IP)

    netop_login()
    custom_validator_valid_post()
    custom_validator_invalid_post()
    delete_bgp_router()

    remove_server_crt()
