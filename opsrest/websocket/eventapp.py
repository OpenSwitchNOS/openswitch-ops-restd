# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from .baseapp import WebSocketBaseApp
from tornado.log import app_log
from opsrest.events import events
from opsrest.events.exceptions import *

WS_APPLICATION_EVENT = 'event'


class WebSocketEventApp(WebSocketBaseApp):
    """
    Event application wrapper over websockets.
    """
    app_type = WS_APPLICATION_EVENT

    def __init__(self, ws):
        self.ws = ws

        if events.get_manager() is None:
            events.set_manager(self.ws.manager)

    def on_open(self):
        app_log.debug("Open received on WebSocket Event")

        # Add callback for subscriber
        try:
            events.add_subscriber(self.ws.id, self.push_notification)
        except EventSubscriptionError as e:
            app_log.error("Error adding subscriber. " + e.details)

    def on_close(self):
        events.remove_subscriber(self.ws.id)

    def on_message(self, message):
        return events.process_msg(self.ws.id, message, self.ws.idl,
                                  self.ws.schema)

    def push_notification(self, _, message):
        app_log.debug("Push notification received from event application")
        self.on_app_send_request(message)
