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

from tornado.log import app_log


class WebSocketBaseApp():
    """
    Base application for websocket applications to derive from.
    """
    app_type = ""

    def __init__(self):
        self.ws = None

    def get_class_name(self):
        return self.__class__.__name__

    def on_open(self, ws):
        app_log.debug("on_open not implemented for " +
                      self.get_class_name())

    def on_close(self, ws):
        app_log.debug("on_close not implemented for " +
                      self.get_class_name())

    def on_message(self, ws, message):
        app_log.debug("on_message not implemented for " +
                      self.get_class_name())

    def on_app_send_request(self, message):
        assert self.ws, "No websocket associated with the application."
        self.ws.send_request(self.app_type, message)
