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

from time import sleep
import http.client
import urllib

from rest_utils_ft import get_switch_ip, rest_sanity_check, \
    execute_request, get_server_crt, remove_server_crt
from rest_utils_ft import LOGIN_URI, DEFAULT_USER, \
    DEFAULT_PASSWORD

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

TEST_HEADER = "/login validation:"
TEST_START = "\n########## " + TEST_HEADER + " %s ##########\n"
TEST_END = "########## End " + TEST_HEADER + " %s ##########\n"

HEADERS = {"Content-type": "application/x-www-form-urlencoded",
           "Accept": "text/plain"}
SWITCH_IP = ""


def query_not_logged_in():
    '''
    This function verifies the user can't query on /login if not logged in
    '''
    test_title = "query login while not logged in"
    print(TEST_START % test_title)

    print("Executing GET on /login while not logged in...")
    status_code, response_data = execute_request(LOGIN_URI, "GET", None,
                                                 SWITCH_IP, False)
    assert status_code == http.client.UNAUTHORIZED
    print(" All good.\n")

    print(TEST_END % test_title)


def successful_login():
    '''
    This verifies Login is successful when using correct data
    '''
    test_title = "successful Login"
    print(TEST_START % test_title)

    data = {'username': DEFAULT_USER, 'password': DEFAULT_PASSWORD}

    # Attempt Login
    print("Attempting login with correct data...")
    response, response_data = execute_request(LOGIN_URI, "POST",
                                              urllib.parse.urlencode(data),
                                              SWITCH_IP, True, HEADERS)
    assert response.status == http.client.OK
    print(" All good.\n")

    # Get cookie header
    cookie_header = {'Cookie': response.getheader('set-cookie')}

    sleep(2)

    # Verify Login was successful
    print("Verifying Login was successful...")
    status_code, response_data = execute_request(LOGIN_URI, "GET", None,
                                                 SWITCH_IP, False,
                                                 cookie_header)
    assert status_code == http.client.OK
    print(" All good.\n")

    print(TEST_END % test_title)


def unsuccessful_login_with_wrong_password():
    '''
    This verifies Login is unsuccessful for an
    existent user but using a wrong password
    '''
    test_title = "unsuccessful Login with wrong password"
    print(TEST_START % test_title)

    data = {'username': DEFAULT_USER, 'password': 'wrongpassword'}

    # Attempt Login
    print("Attempting login with wrong password...")
    response, response_data = execute_request(LOGIN_URI, "POST",
                                              urllib.parse.urlencode(data),
                                              SWITCH_IP, True, HEADERS)
    assert response.status == http.client.UNAUTHORIZED

    print(" All good.\n")

    print(TEST_END % test_title)


def unsuccessful_login_with_non_existent_user():
    '''
    This verifies Login is unsuccessful for a non-existent user
    '''
    test_title = "unsuccessful Login with non-existent user"
    print(TEST_START % test_title)

    data = {'username': 'john', 'password': 'doe'}

    # Attempt Login
    print("Attempting login with non-existent user...")
    response, response_data = execute_request(LOGIN_URI, "POST",
                                              urllib.parse.urlencode(data),
                                              SWITCH_IP, True, HEADERS)
    assert response.status == http.client.UNAUTHORIZED

    print(" All good.\n")

    print(TEST_END % test_title)


def unauthorized_user_login_attempt():
    '''
    This verifies that you can't login with
    a user that has no REST login permissions.
    Current login permissions include
    READ_SWITCH_CONFIG and WRITE_SWITCH_CONFIG.
    Currently, the only users that do not have
    either of these permissions are any user from
    the ops_admin group
    '''
    test_title = "login attempt by unauthorized user"
    print(TEST_START % test_title)

    data = {'username': 'admin', 'password': 'admin'}

    # Attempt Login
    print("Attempting login with an unauthorized user...")
    status_code, response_data = execute_request(LOGIN_URI, "POST",
                                                 urllib.parse.urlencode(data),
                                                 SWITCH_IP, False, HEADERS)
    assert status_code == http.client.UNAUTHORIZED
    print(" All good.\n")

    print(TEST_END % test_title)


def test_ft_login(topology, step):
    sw1 = topology.get('sw1')

    assert sw1 is not None
    global SWITCH_IP

    SWITCH_IP = get_switch_ip(sw1)

    get_server_crt(sw1)
    rest_sanity_check(SWITCH_IP)

    query_not_logged_in()
    successful_login()
    unsuccessful_login_with_wrong_password()
    unsuccessful_login_with_non_existent_user()
    unauthorized_user_login_attempt()

    remove_server_crt()
