# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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

from tornado.ioloop import IOLoop
from tornado import web, gen, locks
from tornado.web import asynchronous
from tornado.concurrent import Future

import json
import httplib
import re

import userauth
from runconfig import runconfig, startupconfig

from opsrest.resource import Resource
from opsrest.parse import parse_url_path
from opsrest.constants import *
from opsrest.utils.utils import *
from opsrest import get, post, delete, put
from opsrest.handlers.base import BaseHandler
from opsrest.settings import settings

from tornado.log import app_log


class ConfigHandler(BaseHandler):

    def prepare(self):
        if settings['auth_enabled']:
            is_authenticated = userauth.is_user_authenticated(self)
        else:
            is_authenticated = True

        if not is_authenticated:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
            self.finish()
        else:
            self.request_type = self.get_argument('type', 'running')
            app_log.debug('request type: %s', self.request_type)

            if self.request_type == 'running':
                self.config_util = runconfig.RunConfigUtil(self.idl,
                                                           self.schema)
            elif self.request_type == 'startup':
                self.config_util = startupconfig.StartupConfigUtil()
            else:
                self.set_status(httplib.BAD_REQUEST)
                self.finish()

    @gen.coroutine
    def get(self):

        result, error = yield self._get_config()
        app_log.debug('Transaction result: %s, Transaction error: %s',
                      result, error)

        if result is None:
            if self.request_type == 'running':
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
            else:
                self.set_status(httplib.NOT_FOUND)
        else:
            self.set_status(httplib.OK)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(json.dumps(result))

        self.finish()

    def _get_config(self):
        waiter = Future()
        waiter.set_result((self.config_util.get_config(), True))
        return waiter

    @gen.coroutine
    def put(self):

        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:

            # get the config
            config_data = json.loads(self.request.body)
            result, error = yield self._write_config(config_data)
            app_log.debug('Transaction result: %s, Transaction error: %s',
                          result, error)

            if result.lower() == 'unchanged':
                self.set_status(httplib.NOT_MODIFIED)
            elif result.lower() == 'success':
                self.set_status(httplib.OK)
            else:
                if type(error) is list:
                    self.write(json.dumps({"error": error}))

                self.set_status(httplib.BAD_REQUEST)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    def _write_config(self, config_data):
        waiter = Future()
        waiter.set_result(self.config_util.write_config_to_db(config_data))
        return waiter
