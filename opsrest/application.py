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

from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop

from ovs.db.idl import Idl
from ovs.db.idl import SchemaHelper
from ovs.poller import Poller

from opsrest.manager import OvsdbConnectionManager
from opslib import restparser
from opsrest import constants
import cookiesecret


class OvsdbApiApplication(Application):
    def __init__(self, settings):
        self.settings = settings
        self.settings['cookie_secret'] = cookiesecret.generate_cookie_secret()
        self.manager = OvsdbConnectionManager(self.settings.get('ovs_remote'),
                                              self.settings.get('ovs_schema'))
        self.restschema = restparser.parseSchema(self.settings.get('ext_schema'))
        self._url_patterns = self._get_url_patterns()
        Application.__init__(self, self._url_patterns, **self.settings)

        # connect to OVSDB using a callback
        IOLoop.current().add_callback(self.manager.start)

    # adds 'self' to url_patterns
    def _get_url_patterns(self):
        from urls import url_patterns
        modified_url_patterns = []
        for url in url_patterns:
            modified_url_patterns.append(url + ({'ref_object': self},))
        return modified_url_patterns
