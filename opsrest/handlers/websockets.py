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

from tornado import websocket
from tornado.log import app_log
from opsrest.websocket.apps import WebSocketAppsContainer
from opsrest.websocket import message as wsmsg
from opsrest.websocket.exceptions import *
import json


class WebSocketHandler(websocket.WebSocketHandler):
    websockets = {}
    curr_id = 0

    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.manager = self.ref_object.manager
        self.schema = self.ref_object.restschema
        self.idl = self.manager.idl
        self.id = self._generate_id()
        self.ws_apps = WebSocketAppsContainer(self)

    def check_origin(self, origin):
        return True

    def open(self):
        WebSocketHandler.websockets[self.id] = self

        self.ws_apps.notify_ws_open()

    def on_close(self):
        app_log.debug("WebSocket close received")

        if self.id in WebSocketHandler.websockets:
            del WebSocketHandler.websockets[self.id]

        self.ws_apps.notify_ws_close()

    def on_message(self, msg_json):
        app_log.debug("Received message: %s" % msg_json)

        app_response_data = None
        error = None
        app_type = None

        try:
            message = json.loads(msg_json)
            wsmsg.validate(message)
            app_type = wsmsg.get_app_type(message)
            app_data = wsmsg.get_app_data(message)

            app_response_data = self.ws_apps.notify_ws_message(app_type,
                                                               app_data)
        except WebSocketException as e:
            error = e.details
            app_log.error(error)

        if app_response_data is not None or error is not None:
            self.send_response(wsmsg.WS_MSG_STATUS_SUCCESS, app_type,
                               app_response_data, error)

    def send_response(self, status, app_type, data, info):
        response = None

        try:
            response = wsmsg.create_response(status, app_type, data, info)
        except WSInvalidMessage as e:
            error = "WebSocket response creation failed. " + e.details
            app_log.error(error)
            response = wsmsg.create_response(wsmsg.WS_MSG_STATUS_ERROR, None,
                                             None, error)

        app_log.debug("Sending response: %s" % response)
        self.write_message(response)

    def send_request(self, app_type, data):
        try:
            request = wsmsg.create_request(app_type, data)

            app_log.debug("Sending request: %s" % request)
            self.write_message(request)
        except WSInvalidMessage as e:
            app_log.error("WebSocket request creation failed. " + e.details)

    def _generate_id(self):
        new_id = WebSocketHandler.curr_id
        WebSocketHandler.curr_id += 1

        return new_id
