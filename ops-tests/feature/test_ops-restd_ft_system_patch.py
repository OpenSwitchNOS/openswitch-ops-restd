# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

import json
import http.client
from rest_utils_ft import execute_request, login, \
    get_switch_ip, rest_sanity_check, get_server_crt, \
    remove_server_crt, get_json

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

TEST_HEADER = "Test to validate PATCH"
TEST_START = "\n########## " + TEST_HEADER + " %s ##########\n"
TEST_END = "########## End " + TEST_HEADER + " %s ##########\n"
cookie_header = None
switch_ip = ""
path = "/rest/v1/system?selector=configuration"


def netop_login():
    global cookie_header
    cookie_header = login(switch_ip)


def check_malformed_json(response_data):
    try:
        data = get_json(response_data)
        return data
    except:
        assert False


def patch_add_new_value():
    # Test Setup
    test_title = "using \"op\": \"add\" with a new value"
    print(TEST_START % test_title)
    data = ["1.1.1.1"]
    patch = [{"op": "add", "path": "/dns_servers", "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)
    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['dns_servers']

    assert post_patch_data == data
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_add_new_value_with_invalid_etag():
    # Test Setup
    test_title = "using \"op\": \"add\" with a new value and invalid etag"
    print(TEST_START % test_title)
    data = ["1.1.1.1"]
    patch = [{"op": "add", "path": "/dns_servers", "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    before_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": "abcdefghijklmnopqrstuvwxyz12345678901234"}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.PRECONDITION_FAILED
    print("### System data remains the same. "
          "Status code 412 PRECONDITION FAILED  ###\n")

    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    after_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    print("Before patch etag: %s\n" % before_patch_etag)
    print("After  patch etag: %s\n" % after_patch_etag)
    assert before_patch_etag == after_patch_etag
    print(TEST_END % test_title)


def patch_add_replace_existing_field():
    # Test Setup
    test_title = "using \"op\": \"add\" replace existing field"
    print(TEST_START % test_title)
    # 1 - Query Resource
    data = ["1.2.3.4"]
    patch = [{"op": "add", "path": "/dns_servers", "value": ["1.1.1.1"]},
             {"op": "add", "path": "/dns_servers", "value": data}]
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK, "Wrong status code %s " % status_code

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['dns_servers']

    assert post_patch_data == data
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_add_an_array_element():
    # Test Setup
    test_title = "using \"op\": \"add\" adding an Array Element"
    print(TEST_START % test_title)
    # 1 - Query Resource
    data = ["1.1.1.1", "1.2.3.4"]
    patch = [{"op": "add", "path": "/dns_servers", "value": ["1.1.1.1"]},
             {"op": "add", "path": "/dns_servers/1", "value": "1.2.3.4"}]
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['dns_servers']

    assert post_patch_data == data
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag, "Etag should not be the same"
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT

    print(TEST_END % test_title)


def patch_add_an_object_member():
    # Test Setup
    test_title = "using \"op\": \"add\" an Object Member"
    print(TEST_START % test_title)
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)
    # 1.1- Modify the Data
    headers = {"If-Match": etag}
    headers.update(cookie_header)

    data = {"baz": "qux"}
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/foo", "value": "bar"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 1.2 Query the resource again
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data: Add a new object member
    patch2 = [{"op": "add", "path": "/other_config/baz", "value": "qux"}]
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch2),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['other_config']

    assert data["baz"] == post_patch_data["baz"]
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/foo"},
             {"op": "remove", "path": "/other_config/baz"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT

    print(TEST_END % test_title)


def patch_add_an_empty_optional_member():
    # Test Setup
    test_title = "using \"op\": \"add\" empty optional member"
    print(TEST_START % test_title)
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data: Add a new object member
    data = {"maxsize": "20"}
    patch2 = [{"op": "add", "path": "/logrotate_config/maxsize",
               "value": "20"}]
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch2),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['logrotate_config']

    assert data["maxsize"] == post_patch_data["maxsize"]
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/logrotate_config/maxsize"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT

    print(TEST_END % test_title)


def patch_add_value_with_malformed_patch():
    # Test Setup
    test_title = "using \"op\": \"add\" field value with malformed patch"
    print(TEST_START % test_title)
    data = ["1.1.1.1"]
    patch = [{"op": "remove", "path": "/dns_servers"},
             {"path": "/dns_servers", "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)

    assert status_code == http.client.BAD_REQUEST
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    post_patch_etag = response.getheader("Etag")
    assert etag == post_patch_etag
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")
    print(TEST_END % test_title)


def patch_add_new_value_for_boolean_field():
    # Test Setup
    test_title = "using \"op\": \"add\" with a new value for boolean field"
    print(TEST_START % test_title)
    data = "true"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/enable-statistics",
             "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']['other_config']

    assert post_patch_data["enable-statistics"] == data
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/enable-statistics"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT

    print(TEST_END % test_title)


def patch_add_multiple_fields():
    # Test Setup
    test_title = "using \"op\": \"add\" multiple fields"
    print(TEST_START % test_title)
    data = ["true", ["1.1.1.1"], "bar"]
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/enable-statistics",
              "value": data[0]},
             {"op": "add", "path": "/dns_servers", "value": data[1]},
             {"op": "add", "path": "/other_config/foo", "value": data[2]}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)

    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)
    post_patch_data = post_patch_data['configuration']

    assert post_patch_data["other_config"]["enable-statistics"] == data[0]
    assert post_patch_data["dns_servers"] == data[1]
    assert post_patch_data["other_config"]["foo"] == data[2]
    post_patch_etag = response.getheader("Etag")
    assert etag != post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/foo"},
             {"op": "remove", "path": "/other_config/enable-statistics"},
             {"op": "remove", "path": "/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT

    print(TEST_END % test_title)


def patch_test_operation_nonexistent_value():
    # Test Setup
    test_title = "using \"op\": \"test\" a nonexistent value"
    print(TEST_START % test_title)
    data = "bar"
    patch = [{"op": "test", "path": "/other_config/foo", "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.BAD_REQUEST
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag == post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)
    print(TEST_END % test_title)


def patch_test_with_malformed_value():
    # Test Setup
    test_title = "using \"op\": \"test\" with a malformed path value"
    print(TEST_START % test_title)
    data = "test data"
    eval_list = ['a/b', '/ab', 'ab/', 'a//b', 'a///b', 'a\\/b']

    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)
    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    headers = {"If-Match": etag}
    headers.update(cookie_header)
    for i in range(len(eval_list)):
        patch = [{"op": "add", "path": "/other_config", "value": {}},
                 {"op": "add", "path": "/other_config/" + eval_list[i],
                  "value": data},
                 {"op": "test", "path": "/other_config/" + eval_list[i],
                  "value": data}]
        print("%s\n" % patch)
        status_code, response_data = execute_request(path, "PATCH",
                                                     json.dumps(patch),
                                                     switch_ip, False,
                                                     headers)
        print("REST API response after evaluate the patch with "
              "string %s in path: %s\n" % (eval_list[i], response_data))
        assert status_code == http.client.BAD_REQUEST

    print("### Configuration data validated ###\n")
    print(TEST_END % test_title)


def patch_test_operation_for_existent_value():
    # Test Setup
    test_title = "using \"op\": \"test\" for existent value"
    print(TEST_START % test_title)
    data = ["1.1.1.1"]
    patch = [{"op": "add", "path": "/dns_servers", "value": data}]
    patch_test = [{"op": "test", "path": "/dns_servers", "value": data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print("### System remains the same. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag == post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_copy_existing_value():
    # Test Setup
    test_title = "using \"op\": \"copy\" for existent value"
    print(TEST_START % test_title)
    data = "this is a test"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/foo", "value": data}]
    patch_test = [{"op": "copy", "from": "/other_config/foo",
                   "path": "/other_config/copy_of_foo"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag != post_patch_etag

    post_patch_data = post_patch_data['configuration']['other_config']
    assert post_patch_data['copy_of_foo'] == post_patch_data['foo']
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/foo"},
             {"op": "remove", "path": "/other_config/copy_of_foo"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_copy_nonexistent_value():
    # Test Setup
    test_title = "using \"op\": \"copy\" for nonexistent value"
    print(TEST_START % test_title)
    patch_test = [{"op": "copy", "from": "/other_config/foo",
                   "path": "/other_config/copy_of_foo"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.BAD_REQUEST
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag == post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)
    print(TEST_END % test_title)


def patch_move_existent_value():
    # Test Setup
    test_title = "using \"op\": \"move\" for existent value"
    print(TEST_START % test_title)
    data = "1.1.1.1"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/servers", "value": data}]
    patch_test = [{"op": "move", "from": "/other_config/servers",
                   "path": "/other_config/dns_servers"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag != post_patch_etag

    post_patch_data = post_patch_data["configuration"]
    assert data == post_patch_data["other_config"]["dns_servers"]

    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/dns_servers"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_move_nonexistent_value():
    # Test Setup
    test_title = "using \"op\": \"move\" a nonexistent value"
    print(TEST_START % test_title)
    patch_test = [{"op": "move", "from": "/other_config/servers",
                   "path": "/other_config/dns_servers"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.BAD_REQUEST
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    assert etag == post_patch_etag
    print(TEST_END % test_title)


def patch_move_value_to_invalid_path():
    # Test Setup
    test_title = "using \"op\": \"move\" value to invalid path"
    print(TEST_START % test_title)
    data = "this is a test"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/abc", "value": data}]
    patch_test = [{"op": "move", "from": "/other_config/abc",
                   "path": "/other_config/abc/def"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.BAD_REQUEST
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag == post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/abc"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_replace_existent_value():
    # Test Setup
    test_title = "using \"op\": \"replace\" for existent value"
    print(TEST_START % test_title)
    data = "foo"
    patch_data = "bar"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/test", "value": data}]
    patch_test = [{"op": "replace", "path": "/other_config/test",
                   "value": patch_data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag != post_patch_etag

    post_patch_data = post_patch_data["configuration"]
    assert patch_data == post_patch_data["other_config"]["test"]
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/test"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_replace_nonexistent_value():
    # Test Setup
    test_title = "using \"op\": \"replace\" for nonexistent value"
    print(TEST_START % test_title)
    data = "foo"
    patch_data = "bar"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/test", "value": data}]
    patch_test = [{"op": "replace",
                   "path": "/other_config/non_existent_field",
                   "value": patch_data}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.BAD_REQUEST
    print("### System remains the same. Status code 400 BAD REQUEST  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag == post_patch_etag
    print("### Configuration data validated %s ###\n" % post_patch_data)

    # Test Teardown
    headers = {"If-Match": post_patch_etag}
    headers.update(cookie_header)
    patch = [{"op": "remove", "path": "/other_config/test"}]
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch), switch_ip,
                                                 xtra_header=headers)

    assert status_code == http.client.NO_CONTENT
    print(TEST_END % test_title)


def patch_remove_existent_value():
    # Test Setup
    test_title = "using \"op\": \"remove\" for existent value"
    print(TEST_START % test_title)
    data = "foo"
    patch = [{"op": "add", "path": "/other_config", "value": {}},
             {"op": "add", "path": "/other_config/test", "value": data}]
    patch_test = [{"op": "remove", "path": "/other_config/test"}]
    # 1 - Query Resource
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    check_malformed_json(response_data)

    # Test
    # 2 - Modify data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    etag = response.getheader("Etag")
    status_code = response.status
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 2.1 - Test data
    headers = {"If-Match": etag}
    headers.update(cookie_header)
    status_code, response_data = execute_request(path, "PATCH",
                                                 json.dumps(patch_test),
                                                 switch_ip, False,
                                                 headers)
    assert status_code == http.client.NO_CONTENT
    print("### System Modified. Status code 204 NO CONTENT  ###\n")

    # 3 - Verify Modified data
    response, response_data = execute_request(path, "GET", None, switch_ip,
                                              True, xtra_header=cookie_header)

    post_patch_etag = response.getheader("Etag")
    status_code = response.status
    assert status_code == http.client.OK

    post_patch_data = check_malformed_json(response_data)

    assert etag != post_patch_etag

    # If "test" was the last value in other_config,
    # GET will not return the column at all if removed
    if "other_config" in post_patch_data["configuration"]:
        assert "test" not in post_patch_data["configuration"]["other_config"]

    print("### Configuration data validated %s ###\n" % post_patch_data)
    print(TEST_END % test_title)


def test_patch_system(topology, step):
    sw1 = topology.get('sw1')

    assert sw1 is not None
    global switch_ip

    switch_ip = get_switch_ip(sw1)

    get_server_crt(sw1)
    rest_sanity_check(switch_ip)

    netop_login()
    patch_add_new_value()

    netop_login()
    patch_add_replace_existing_field()

    netop_login()
    patch_add_an_array_element()

    netop_login()
    patch_add_an_object_member()

    netop_login()
    patch_add_an_empty_optional_member()

    netop_login()
    patch_add_value_with_malformed_patch()

    netop_login()
    patch_add_new_value_for_boolean_field()

    netop_login()
    patch_add_multiple_fields()

    netop_login()
    patch_test_operation_nonexistent_value()

    netop_login()
    patch_test_with_malformed_value()

    netop_login()
    patch_test_operation_for_existent_value()

    netop_login()
    patch_copy_existing_value()

    netop_login()
    patch_copy_nonexistent_value()

    netop_login()
    patch_move_existent_value()

    netop_login()
    patch_move_nonexistent_value()

    netop_login()
    patch_move_value_to_invalid_path()

    netop_login()
    patch_replace_existent_value()

    netop_login()
    patch_replace_nonexistent_value()

    netop_login()
    patch_remove_existent_value()

    netop_login()
    patch_add_new_value_with_invalid_etag()

    remove_server_crt()
