# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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

import re
import userauth
import httplib

from tornado import web
from opsrest.constants import *
from opsrest.exceptions import APIException
from opsrest.settings import settings

from tornado.log import app_log


class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl
        self.request.path = re.sub("/{2,}", "/", self.request.path).rstrip('/')

    def set_default_headers(self):
        # CORS
        allow_origin = self.request.protocol + "://"
        # removing port if present
        allow_origin += self.request.host.split(":")[0]
        self.set_header("Cache-control", "no-cache")
        self.set_header("Access-Control-Allow-Origin", allow_origin)
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Expose-Headers", "Date,%s" %
                        HTTP_HEADER_ETAG)
        self.set_header("Access-Control-Request-Headers",
                        HTTP_HEADER_CONDITIONAL_IF_MATCH)

        # TODO - remove next line before release - needed for testing
        if HTTP_HEADER_ORIGIN in self.request.headers:
            self.set_header("Access-Control-Allow-Origin",
                            self.request.headers[HTTP_HEADER_ORIGIN])

    def prepare(self):

        app_log.debug("Incoming request from %s: %s",
                      self.request.remote_ip,
                      self.request)

        if settings['auth_enabled'] and self.request.method != "OPTIONS":
            is_authenticated = userauth.is_user_authenticated(self)
        else:
            is_authenticated = True

        if not is_authenticated:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
            self.finish()

    def get_current_user(self):
        return userauth.get_request_user(self)

    def on_exception(self, e):

        app_log.debug(e)
        if self.txn is not None:
            self.txn.abort()

        # uncaught exceptions
        if not isinstance(e, APIException):
            self.set_status(httplib.INTERNAL_SERVER_ERROR)
        else:
            self.set_status(e.status_code)

        self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
        self.write(str(e))
