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

from .eventapp import *
from .exceptions import WSInvalidApplication

# WebSocket Applications
_g_ws_app_types = {WS_APPLICATION_EVENT: WebSocketEventApp}


class WebSocketAppsContainer:
    """
    Container for websocket applications. Notifies all applications of
    websocket events.
    """
    def __init__(self, ws):
        assert ws, "Invalid websocket"
        self.ws = ws
        self.ws_apps = {}

        # Initialize all applications
        for app_type, app_class in _g_ws_app_types.iteritems():
            self.ws_apps[app_type] = app_class(ws)

    def _get_app_instance(self, app_type):
        if app_type not in self.ws_apps:
            raise WSInvalidApplication("Invalid app " + app_type)

        return self.ws_apps[app_type]

    def notify_ws_close(self):
        '''
        Notifies websocket applications that the websocket has closed.
        '''
        for ws_app in self.ws_apps.values():
            ws_app.on_close()

    def notify_ws_open(self):
        '''
        Notifies websocket applications that the websocket has opened.
        '''
        for ws_app in self.ws_apps.values():
            ws_app.on_open()

    def notify_ws_message(self, app_type, app_data):
        '''
        Returns the response originated from the application after notifying
        the websocket application that the websocket has received a message.
        '''
        ws_app = self._get_app_instance(app_type)
        return ws_app.on_message(app_data[app_type])
