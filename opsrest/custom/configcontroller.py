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

# Local imports
from runconfig import runconfig, startupconfig

from opsrest.exceptions import DataValidationFailed,\
    NotModified, TransactionFailed, InternalError,\
    NotFound
from opsrest.custom.basecontroller import BaseController
from opsrest.constants import CONFIG_TYPE_RUNNING,\
    CONFIG_TYPE_STARTUP


class ConfigController(BaseController):

    def initialize(self):
        self.base_uri_path = "system/full-configuration"
        self.idl = self.context.manager.idl
        self.schema = self.context.restschema

    def update(self, item_id, data, current_user, query_args):
        request_type = self.get_request_type(query_args)
        config_util = self.get_config_util(request_type)
        result, error = config_util.write_config_to_db(data)
        if result.lower() == 'unchanged':
            raise NotModified
        if type(error) is list:
            raise DataValidationFailed(error)

    def get_all(self, current_user, selector, query_args):
        request_type = self.get_request_type(query_args)
        config_util = self.get_config_util(request_type)
        result = config_util.get_config()
        if result is None:
            if request_type == CONFIG_TYPE_RUNNING:
                raise InternalError
            else:
                raise NotFound
        return result

    def get_request_type(self, query_args={}):
        _type = query_args.get("type", CONFIG_TYPE_RUNNING)
        if isinstance(_type, list):
            _type = _type[0]

        return _type

    def get_config_util(self, request_type):
        app_log.debug('Requested config type: %s', request_type)
        if request_type == CONFIG_TYPE_RUNNING:
            return runconfig.RunConfigUtil(self.idl, self.schema)
        elif request_type == CONFIG_TYPE_STARTUP:
            return startupconfig.StartupConfigUtil()
        else:
            error = "Invalid configuration type. Configuration "\
                    "types allowed: %s, %s" %\
                    (CONFIG_TYPE_RUNNING, CONFIG_TYPE_STARTUP)
            raise DataValidationFailed(error)
