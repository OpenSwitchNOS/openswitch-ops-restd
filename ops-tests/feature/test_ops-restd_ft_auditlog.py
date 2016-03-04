# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Openswitch Test for Auditlog
"""

import pytest
from pytest import mark
from time import sleep
import http.client


TOPOLOGY = """
# +-------+      +-------+
# |  hs1   <----->  ops1  |
# +-------+      +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=host name="Host 1"] hs1
[force_name=mgmt] ops1:1

# Links
hs1:1 -- ops1:1
"""


DEFAULT_USER = 'netop'
DEFAULT_PASSWORD = 'netop'
switch_ip = '10.0.10.1'
host_ip = '10.0.10.100'
cookie = None


def fast_clean_auditlog(ops1):
    ops1('echo > /var/log/audit/audit.log;', shell='bash')


def curl_event(rest_server_ip, method, url, command, cookie=None, data=None):
    '''
    Generates the curl command.
    This method should be replaced whenthe REST library for the
    Modular Test Framework is available.
    '''
    curl_command = ('curl -v -k -H \"Content-Type: application/json\" '
                    '--retry 3 ')
    curl_xmethod = '-X ' + method + ' '
    curl_url = '\"https://' + rest_server_ip + url + '\" '
    curl_command += curl_xmethod

    if (cookie):
        curl_command += '--cookie \'' + cookie + '\' '
    if (data):
        curl_command += '-d \'' + data + '\' '

    curl_command += curl_url

    if (command):
        curl_command += command

    return curl_command


def get_status_code(request_output):
    '''
    Method returns the status code by parsing the curl output
    '''
    request_output = request_output.split('\n')[1]
    return int(request_output[request_output.index('HTTP/1.1'):].split(' ')[1])


@pytest.fixture(scope="module")
@mark.platform_incompatible(['docker'])
def setup(topology, request):
    """
    Set network address
    """
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')

    assert ops1 is not None
    assert hs1 is not None

    # Configure IP and bring UP host 1 interface and ops 1 interface
    ops1.libs.ip.interface('1', addr=switch_ip + '/24', up=True, shell='bash')
    hs1.libs.ip.interface('1', addr=host_ip + '/24', up=True)

    # Clean bridges
    bridges = ops1('list-br', shell='vsctl').split('\n')
    for bridge in bridges:
        if bridge != 'bridge_normal':
            ops1('del-br {bridge}'.format(**locals()), shell='vsctl')

    # Restart Restd & AuditLog daemons / Clean log files
    ops1('systemctl daemon-reload; systemctl stop restd; '
         'echo > /var/log/messages; systemctl start restd; '
         'systemctl stop auditd; '
         'echo > /var/log/audit/audit.log; '
         'systemctl start auditd', shell='bash')

    # Wait 5 seconds for daemons to restart
    sleep(5)

    # Getting the login cookie
    fast_clean_auditlog(ops1)
    login_curl = curl_event(switch_ip, 'POST',
                            '/login?username=' + DEFAULT_USER +
                            ';password=' + DEFAULT_PASSWORD,
                            '2>&1 | grep Set-Cookie')
    login_post = hs1(login_curl, shell='bash')

    global cookie
    cookie = login_post[login_post.index('user='):]
    assert len(cookie) > 0, "The login cookie is invalid"

    # Verify in Auditlog / Ausearch the Login event
    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:POST' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=success' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    def fin():
        ops1.libs.ip.remove_ip('1', addr=switch_ip + '/24', shell='bash')
        hs1.libs.ip.remove_ip('1', addr=host_ip + '/24')
    request.addfinalizer(fin)


@mark.platform_incompatible(['docker'])
def test_auditlog_post_bridge_success(topology, setup):
    # Test 1. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    fast_clean_auditlog(ops1)
    post_bridge = curl_event(switch_ip, 'POST',
                             '/rest/v1/system/bridges',
                             '2>&1 | grep "< HTTP/1.1 "', cookie,
                             '{"configuration": '
                             '{"datapath_type": "", "name": "br0"}}')

    # Test 1. Verify in Auditlog / Ausearch the Bridge POST event success
    status_code = get_status_code(hs1(post_bridge, shell='bash'))
    assert status_code == http.client.CREATED, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:POST' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=success' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 1. Teardown
    ops1('del-br br0', shell='vsctl')


@mark.platform_incompatible(['docker'])
def test_auditlog_post_bridge_failed(topology, setup):
    # Test 2. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    post_bridge = curl_event(switch_ip, 'POST',
                             '/rest/v1/system/bridges',
                             '2>&1 | grep "< HTTP/1.1 "', cookie,
                             '{"configuration": '
                             '{"datapath_type": "", "name": "br0"}}')

    # Test 2. Verify in Auditlog / Ausearch the Bridge POST event failed
    status_code = get_status_code(hs1(post_bridge, shell='bash'))
    assert status_code == http.client.BAD_REQUEST, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:POST' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=failed' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 2. Teardown
    ops1('del-br br0', shell='vsctl')


@mark.platform_incompatible(['docker'])
def test_auditlog_put_bridge_success(topology, setup):
    # Test 3. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    put_bridge = curl_event(switch_ip, 'PUT',
                            '/rest/v1/system/bridges/br0',
                            '2>&1 | grep "< HTTP/1.1 "', cookie,
                            '{"configuration": '
                            '{"datapath_type": "bridge", "name": "br0"}}')

    # Test 3. Verify in Auditlog / Ausearch the Bridge PUT event success
    status_code = get_status_code(hs1(put_bridge, shell='bash'))
    assert status_code == http.client.OK, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:PUT' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=success' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 3. Teardown
    ops1('del-br br0', shell='vsctl')


@mark.platform_incompatible(['docker'])
def test_auditlog_put_bridge_failed(topology, setup):
    # Test 4. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    put_bridge = curl_event(switch_ip, 'PUT',
                            '/rest/v1/system/bridges',
                            '2>&1 | grep "< HTTP/1.1 "', cookie,
                            '{"configuration": '
                            '{"datapath_type": "bridge", "name": "br0"}}')

    # Test 4. Verify in Auditlog / Ausearch the Bridge PUT event failed
    status_code = get_status_code(hs1(put_bridge, shell='bash'))
    assert status_code == http.client.METHOD_NOT_ALLOWED, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:PUT' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=failed' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 4. Teardown
    ops1('del-br br0', shell='vsctl')


@mark.platform_incompatible(['docker'])
def test_auditlog_delete_bridge_success(topology, setup):
    # Test 5. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    delete_bridge = curl_event(switch_ip, 'DELETE',
                               '/rest/v1/system/bridges/br0',
                               '2>&1 | grep "< HTTP/1.1 "', cookie)

    # Test 5. Verify in Auditlog / Ausearch the Bridge DELETE event success
    status_code = get_status_code(hs1(delete_bridge, shell='bash'))
    assert status_code == http.client.NO_CONTENT, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:DELETE' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=success' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'


@mark.platform_incompatible(['docker'])
def test_auditlog_delete_bridge_failed(topology, setup):
    # Test 6. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    fast_clean_auditlog(ops1)
    delete_bridge = curl_event(switch_ip, 'DELETE',
                               '/rest/v1/system/bridges/br100',
                               '2>&1 | grep "< HTTP/1.1 "', cookie)

    # Test 6. Verify in Auditlog / Ausearch the Bridge DELETE event failed
    status_code = get_status_code(hs1(delete_bridge, shell='bash'))
    assert status_code == http.client.NOT_FOUND, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:DELETE' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=failed' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'


@mark.platform_incompatible(['docker'])
def test_auditlog_patch_bridge_success(topology, setup):
    # Test 7. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    put_bridge = curl_event(switch_ip, 'PATCH',
                            '/rest/v1/system/bridges/br0',
                            '2>&1 | grep "< HTTP/1.1 "', cookie,
                            '[{"op": "add", "path": "/datapath_type", '
                            '"value": "bridge"}]')

    # Test 7. Verify in Auditlog / Ausearch the Bridge PUT event success
    status_code = get_status_code(hs1(put_bridge, shell='bash'))
    assert status_code == http.client.NO_CONTENT, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:PATCH' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=success' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 7. Teardown
    ops1('del-br br0', shell='vsctl')


@mark.platform_incompatible(['docker'])
def test_auditlog_patch_bridge_failed(topology, setup):
    # Test 8. Setup
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    ops1('add-br br0', shell='vsctl')
    fast_clean_auditlog(ops1)
    put_bridge = curl_event(switch_ip, 'PATCH',
                            '/rest/v1/system/bridges/br0',
                            '2>&1 | grep "< HTTP/1.1 "', cookie,
                            '[{"op": "add", "path": "/nonexistent_path", '
                            '"value": "bridge"}]')

    # Test 8. Verify in Auditlog / Ausearch the Bridge PUT event success
    status_code = get_status_code(hs1(put_bridge, shell='bash'))
    assert status_code == http.client.BAD_REQUEST, 'Wrong status code'

    ausearch = ops1('ausearch -i', shell='bash').split('\n')
    for line in ausearch:
        if ('type=USYS_CONFIG' in line and 'op=RESTD:PATCH' in line):
            assert 'user=' + DEFAULT_USER in line, 'Wrong User'
            assert 'res=failed' in line, 'Wrong result'
            assert 'addr=' + host_ip in line, 'Wrong host ip address'

    # Test 8. Teardown
    ops1('del-br br0', shell='vsctl')
