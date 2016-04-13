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
from tornado import gen

# Local imports
import ops.dc
import ops.cfgd
from opsrest.exceptions import DataValidationFailed,\
    NotModified, InternalError, NotFound, APIException,\
    MethodNotAllowed
from opsrest.transaction import OvsdbTransactionResult
from opsrest.custom.basecontroller import BaseController
from opsrest.patch import create_patch, apply_patch
from opsrest.constants import CONFIG_TYPE_RUNNING,\
    CONFIG_TYPE_STARTUP, SUCCESS, UNCHANGED, INCOMPLETE


class ConfigController(BaseController):

    def initialize(self):
        self.idl = self.context.manager.idl
        self.schema = self.context.restschema
        self.txn = None

    @gen.coroutine
    def update(self, item_id, data, current_user, query_args):
        try:
            request_type = self.get_request_type(query_args)
            self.check_config_type(request_type)
            status = None
            error = None
            if request_type == CONFIG_TYPE_RUNNING:
                self.txn = self.context.manager.get_new_transaction()
                result = OvsdbTransactionResult(ops.dc.write(data, self.schema,
                                                             self.idl,
                                                             self.txn.txn))
                status = result.status
                app_log.debug('Transaction result: %s', status)
                if status == INCOMPLETE:
                    self.context.manager.monitor_transaction(self.txn)
                    yield self.txn.event.wait()
                    status = self.txn.status
            else:
                # FIXME: This is a blocking call.
                (status, error) = ops.cfgd.write(data)
            if status != SUCCESS:
                if status == UNCHANGED:
                    raise NotModified
                else:
                    if request_type == CONFIG_TYPE_RUNNING:
                        error = self.txn.get_error()
                        self.txn.abort()
                    raise APIException("Error: %s" % error)
        except Exception as e:
            if self.txn:
                self.txn.abort()
            raise APIException("Error: %s" % str(e))

    @gen.coroutine
    def get_all(self, current_user, selector, query_args):
        request_type = self.get_request_type(query_args)
        self.check_config_type(request_type)
        result = None
        if request_type == CONFIG_TYPE_RUNNING:
            result = ops.dc.read(self.schema, self.idl)
        else:
            # FIXME: This is a blocking call
            result = ops.cfgd.read()
        if result is None:
            if request_type == CONFIG_TYPE_RUNNING:
                raise InternalError
            else:
                raise NotFound
        return result

    def get_request_type(self, query_args):
        app_log.debug('Query args: %s', query_args)
        if not query_args:
            return CONFIG_TYPE_RUNNING
        else:
            typearg = query_args.get("type", CONFIG_TYPE_RUNNING)
            return typearg[0]

    def check_config_type(self, request_type):
        app_log.debug('Requested config type: %s', request_type)
        if request_type not in [CONFIG_TYPE_RUNNING, CONFIG_TYPE_STARTUP]:
            error = "Invalid configuration type. Configuration "\
                    "types allowed: %s, %s" %\
                    (CONFIG_TYPE_RUNNING, CONFIG_TYPE_STARTUP)
            raise DataValidationFailed(error)

    @gen.coroutine
    def patch(self, item_id, data, current_user=None, query_args=None):
        try:
            # Get the resource's JSON to patch
            resource_json = yield self.get_all(current_user, None, query_args)

            if resource_json is None:
                raise NotFound

            # Create and verify patch
            (patch, needs_update) = create_patch(data)

            # Apply patch to the resource's JSON
            patched_resource = apply_patch(patch, resource_json)

            # Update resource only if needed, since a valid
            # patch can contain PATCH_OP_TEST operations
            # only, which do not modify the resource
            if needs_update:
                yield self.update(item_id, patched_resource, current_user, query_args)

        # In case the resource doesn't implement GET/PUT
        except MethodNotAllowed:
            raise MethodNotAllowed("PATCH not allowed on resource")
