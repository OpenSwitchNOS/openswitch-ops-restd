#!/usr/bin/env python
#
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

from opsvsi.docker import *
from opsvsi.opsvsitest import *
from tornado import testing, websocket
from copy import deepcopy
from opsvsiutils.restutils import utils, eventutils as evutils
import httplib

WS_PORT = 8091
WS_PATH = 'ws'

TEST_PORT_PATH = "/rest/v1/system/ports/Port1"

TABLE_EVENT_SUBSCRIPTION = {
    "event_id": "1",
    "type": "table",
    "resource": "Port"
}

ROW_EVENT_SUBSCRIPTION = {
    "event_id": "2",
    "type": "row",
    "resource": TEST_PORT_PATH,
}


class WebSocketEventTest(OpsVsiTest):
    def setupNet(self):
        self.net = Mininet(topo=SingleSwitchTopo(k=0, hopts=self.getHostOpts(),
                                                 sopts=self.getSwitchOpts()),
                           switch=VsiOpenSwitch,
                           host=Host,
                           link=OpsVsiLink,
                           controller=None,
                           build=True)

        self.switch = self.net.switches[0]
        self.switch_ip = utils.get_switch_ip(self.switch)


class TestWebSocketEvents(testing.AsyncTestCase):
    def setup(self):
        pass

    def setUp(self):
        super(TestWebSocketEvents, self).setUp()

    def teardown(self):
        pass

    def setup_class(cls):
        TestWebSocketEvents.test_var = WebSocketEventTest()

    def teardown_class(cls):
        TestWebSocketEvents.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        # Issuing delete just in case any tests fail and there is lingering
        # test data, which may cause subsequent tests to fail.
        self._delete_test_port()

    def create_connection(cls):
        ws_uri = 'ws://%s:%s/%s' % (cls.test_var.switch_ip, WS_PORT, WS_PATH)
        info("### Creating connection to %s ###\n" % ws_uri)
        return websocket.websocket_connect(ws_uri)

    def __del__(self):
        del self.test_var

    def _create_and_verify_test_port(self):
        info("### Creating test port ###\n")
        status_code, response = utils.create_test_port(self.test_var.switch_ip)
        assert status_code == httplib.CREATED, "Port not created."

        info("### Test port created ###\n")

    def _delete_test_port(self):
        return utils.execute_request(TEST_PORT_PATH, "DELETE", None,
                                     self.test_var.switch_ip)

    def _delete_test_port_and_verify(self):
        info("### Deleting test port ###\n")

        status_code, response = self._delete_test_port()
        assert status_code == httplib.NO_CONTENT, \
            "Unexpected status code %s" % status_code

        info("### Test port deleted successfully ###\n")

    def _update_port_field(self, path, field, new_value):
        info("### Updating field to trigger notification ###\n")
        info("### Path: %s, field: %s, value: %s ###\n" %
             (path, field, new_value))

        utils.update_test_field(self.test_var.switch_ip, path,
                                field, new_value)

    @testing.gen_test
    def test_subscribe_to_row_specific_column_changes(self):
        info("\n########## Testing subscription to specific "
             "column changes ##########\n")

        conn = yield self.create_connection()

        # Create the test data for subscribing to a row for changes
        self._create_and_verify_test_port()

        # Specify specific field to subscribe to
        subscribed_field = 'trunks'
        event_subscription = ROW_EVENT_SUBSCRIPTION
        evutils.set_subscribed_fields(event_subscription, [subscribed_field])
        subscriptions_list = [event_subscription]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Update a field for the row to trigger a notification
        path = evutils.get_subscription_resource(event_subscription)
        self._update_port_field(path, subscribed_field, [400])

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_subscribe_to_row_all_column_changes(self):
        info("\n########## Testing subscription to all "
             "column changes ##########\n")

        conn = yield self.create_connection()

        # Create the test data for subscribing to a row for changes
        self._create_and_verify_test_port()

        # Subscribe to a row
        event_subscription = ROW_EVENT_SUBSCRIPTION

        # Set empty fields to register for all columns
        evutils.set_subscribed_fields(event_subscription, [])
        subscriptions_list = [ROW_EVENT_SUBSCRIPTION]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Update a field for the row to trigger a notification
        path = evutils.get_subscription_resource(event_subscription)
        self._update_port_field(path, 'trunks', [400])

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_subscribe_to_multiple_resource_single_request(self):
        info("\n########## Testing subscription to multiple resources in a "
             "single request ##########\n")

        conn = yield self.create_connection()

        # Create the test data for subscribing to a row for changes
        self._create_and_verify_test_port()

        # Specify subscriptions
        event_subscription = ROW_EVENT_SUBSCRIPTION
        subscribed_field = 'trunks'
        evutils.set_subscribed_fields(event_subscription, [subscribed_field])
        subscriptions_list = [TABLE_EVENT_SUBSCRIPTION, ROW_EVENT_SUBSCRIPTION]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Update a field for the row to trigger a notification
        path = evutils.get_subscription_resource(event_subscription)
        self._update_port_field(path, subscribed_field, [400])

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_subscribe_to_multiple_resource_multiple_requests(self):
        info("\n########## Testing subscription to multiple resources in "
             "multiple requests ##########\n")

        conn = yield self.create_connection()

        # Create the test data for subscribing to a row for changes
        self._create_and_verify_test_port()

        # Subscribe to table events
        subscriptions_list = []
        info("### Subscribing to table events ###\n")
        event_subscription = TABLE_EVENT_SUBSCRIPTION
        subscriptions_list.append(event_subscription)
        req = evutils.create_ws_event_subs_req_json([event_subscription])
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Subscribe to row events
        info("### Subscribing to row events ###\n")
        event_subscription = ROW_EVENT_SUBSCRIPTION
        subscribed_field = 'trunks'
        evutils.set_subscribed_fields(event_subscription, [subscribed_field])
        subscriptions_list.append(event_subscription)
        req = evutils.create_ws_event_subs_req_json([event_subscription])
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Update a field for the row to trigger a notification for both
        # subscriptions
        path = evutils.get_subscription_resource(event_subscription)
        self._update_port_field(path, subscribed_field, [400])

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_subscribe_to_table_changes_row_added(self):
        info("\n########## Testing subscription to a table and a row "
             "is added ##########\n")

        conn = yield self.create_connection()

        # Specify table to subscribe to
        subscriptions_list = [TABLE_EVENT_SUBSCRIPTION]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Add a new entry in the table to trigger the table notification
        info("### Adding entry to the table to trigger notification ###\n")
        self._create_and_verify_test_port()

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_subscribe_to_table_changes_row_deleted(self):
        info("\n########## Testing subscription to a table and a row "
             "is deleted ##########\n")

        conn = yield self.create_connection()

        # Add a new entry in the table to trigger the table notification
        self._create_and_verify_test_port()

        # Specify table to subscribe to
        subscriptions_list = [TABLE_EVENT_SUBSCRIPTION]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Delete the port created
        info("### Deleting port to trigger notification ###\n")
        self._delete_test_port_and_verify()

        # Wait for the event notification and verify
        info("### Waiting for event notification ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Close websocket connection
        conn.close()

    @testing.gen_test
    def test_subscribe_to_table_changes_row_updated(self):
        info("\n########## Testing subscription to a table and a row "
             "is updated ##########\n")

        conn = yield self.create_connection()

        # Subscribe to the table
        subscriptions_list = [TABLE_EVENT_SUBSCRIPTION]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = True
        evutils.validate_ws_event_message(response, is_request,
                                          validate_success)

        # Create the test data
        self._create_and_verify_test_port()

        # Wait for the event notification and verify
        info("### Waiting for the first event notification for adding ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Update a field for the row to trigger a notification
        self._update_port_field(TEST_PORT_PATH, 'trunks', [400])

        # Wait for the event notification and verify
        info("### Waiting for the second event notification for "
             "updating ###\n")
        notif_req_json = yield conn.read_message()
        notif_data = evutils.validate_event_notification(notif_req_json)
        evutils.verify_notifications_recv(subscriptions_list, notif_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_negative_subscribe_to_invalid_row_column(self):
        info("\n########## Negative testing by subscribing to an invalid "
             "column ##########\n")

        conn = yield self.create_connection()

        # Create the test data for subscribing to a row for changes
        self._create_and_verify_test_port()

        # Specify specific field to subscribe to
        info("### Setting invalid column name for subscription request ###\n")
        invalid_column = 'invalid_column'
        event_subscription = ROW_EVENT_SUBSCRIPTION
        evutils.set_subscribed_fields(event_subscription, [invalid_column])
        subscriptions_list = [event_subscription]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = False
        response_data = evutils.validate_ws_event_message(response,
                                                          is_request,
                                                          validate_success)

        # Verify errors received
        event_id = evutils.get_event_id(event_subscription)
        evutils.verify_subscription_error(event_id, invalid_column,
                                          response_data)

        # Delete the port created for testing and close websocket connection
        self._delete_test_port_and_verify()
        conn.close()

    @testing.gen_test
    def test_negative_subscribe_to_invalid_table(self):
        info("\n########## Negative testing by subscribing to an invalid "
             "table ##########\n")

        conn = yield self.create_connection()

        # Specify specific field to subscribe to
        info("### Setting invalid table name for subscription request ###\n")
        invalid_table = 'InvalidTable'
        event_subscription = deepcopy(TABLE_EVENT_SUBSCRIPTION)
        evutils.set_subscription_resource(event_subscription, invalid_table)
        subscriptions_list = [event_subscription]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = False
        response_data = evutils.validate_ws_event_message(response,
                                                          is_request,
                                                          validate_success)

        # Verify errors received
        event_id = evutils.get_event_id(event_subscription)
        evutils.verify_subscription_error(event_id, invalid_table,
                                          response_data)

        # Close websocket connection
        conn.close()

    @testing.gen_test
    def test_negative_subscribe_to_invalid_row(self):
        info("\n########## Negative testing by subscribing to an invalid "
             "row ##########\n")

        conn = yield self.create_connection()

        # Specify specific field to subscribe to
        info("### Setting invalid row for subscription request ###\n")
        invalid_row = TEST_PORT_PATH + "Invalid"
        event_subscription = deepcopy(ROW_EVENT_SUBSCRIPTION)
        evutils.set_subscribed_fields(event_subscription, [])
        evutils.set_subscription_resource(event_subscription, invalid_row)
        subscriptions_list = [event_subscription]
        req = evutils.create_ws_event_subs_req_json(subscriptions_list)
        conn.write_message(req)

        # Obtain a response from subscribing
        info("### Waiting for a response for the subscription ###\n")
        response = yield conn.read_message()
        is_request = False
        validate_success = False
        response_data = evutils.validate_ws_event_message(response,
                                                          is_request,
                                                          validate_success)

        # Verify errors received
        event_id = evutils.get_event_id(event_subscription)
        evutils.verify_subscription_error(event_id, invalid_row, response_data)

        # Close websocket connection
        conn.close()
