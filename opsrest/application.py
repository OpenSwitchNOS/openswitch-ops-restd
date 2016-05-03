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

from tornado.web import Application, StaticFileHandler
from tornado.log import app_log

from opsrest.exceptions import InternalError
from opsrest.manager import OvsdbConnectionManager
from opslib import restparser
from opsrest import constants
from opsvalidator import validator
import cookiesecret
import yaml


class OvsdbApiApplication(Application):
    def __init__(self, settings):
        self.settings = settings
        self.settings['cookie_secret'] = cookiesecret.generate_cookie_secret()
        self.manager = OvsdbConnectionManager(self.settings.get('ovs_remote'),
                                              self.settings.get('ovs_schema'))
        schema = self.settings.get('ext_schema')
        self.restschema = restparser.parseSchema(schema)
        self._url_patterns = self._get_url_patterns()
        self.passwd_srv_sock_fd = None
        self.passwd_srv_pub_key_loc = None
        self.__get_passwd_srv_files_location__()
        Application.__init__(self, self._url_patterns, **self.settings)

        # We must block the application start until idl connection
        # and replica is ready
        self.manager.start()

        # Load all custom validators
        validator.init_plugins(constants.OPSPLUGIN_DIR)

    # adds 'self' to url_patterns
    def _get_url_patterns(self):
        from urls import url_patterns
        from urls import custom_url_patterns
        from urls import static_url_patterns

        modified_url_patterns = []

        for url, handler, controller_class in custom_url_patterns:
            params = {'ref_object': self, 'controller_class': controller_class}
            modified_url_patterns.append((url, handler, params))

        for url in url_patterns:
            modified_url_patterns.append(url + ({'ref_object': self},))

        modified_url_patterns.extend(static_url_patterns)

        return modified_url_patterns

    def __get_passwd_srv_files_location__(self):
        try:
            passwd_srv_yaml = open(self.settings.get('passwd_srv_yaml'), "r")
            passwd_srv_files = yaml.load_all(passwd_srv_yaml)
            for files in passwd_srv_files:
                for k, v in files.items():
                    passwd_srv_list = v
            for element in passwd_srv_list:
                if element['type'] == constants.PASSWD_SRV_SOCK_TYPE_KEY:
                    self.passwd_srv_sock_fd = element['path']
                if element['type'] == constants.PASSWD_SRV_PUB_TYPE_KEY:
                    self.passwd_srv_pub_key_loc = element['path']
            passwd_srv_yaml.close()
        except Exception as e:
            app_log.debug("Failed to open Password Server YAML file: %s" % e)
            raise InternalError(constants.PASSWD_SRV_GENERIC_ERR)
