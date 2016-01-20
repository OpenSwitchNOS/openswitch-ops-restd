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

from tornado import gen
from tornado.log import app_log

import json
import httplib
import hashlib

from opsrest.handlers import base
from opsrest.parse import parse_url_path
from opsrest.utils import utils
from opsrest.constants import *
from opsrest.exceptions import APIException

from opsrest import get, post, delete, put


class OVSDBAPIHandler(base.BaseHandler):

    # parse the url and http params.
    def prepare(self):

        # Call parent's prepare to check authentication
        super(OVSDBAPIHandler, self).prepare()

        self.resource_path = parse_url_path(self.request.path,
                                            self.schema,
                                            self.idl,
                                            self.request.method)

        if self.resource_path is None:
            self.set_status(httplib.NOT_FOUND)
            self.finish()
        else:
            # If Match support
            match = self.process_if_match()
            if not match:
                self.finish()

    def on_finish(self):
        app_log.debug("Finished handling of request from %s",
                      self.request.remote_ip)

    def compute_etag(self, data=None):
        if data is None:
            return super(OVSDBAPIHandler, self).compute_etag()

        hasher = hashlib.sha1()
        for element in data:
            hasher.update(element)
        return '"%s"' % hasher.hexdigest()

    def process_if_match(self):
        if HTTP_HEADER_CONDITIONAL_IF_MATCH in self.request.headers:
            selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)
            result = get.get_resource(self.idl, self.resource_path,
                                      self.schema, self.request.path,
                                      selector, self.request.query_arguments)
            if result is None:
                self.set_status(httplib.PRECONDITION_FAILED)
                return False

            match = False
            etags = self.request.headers.get(HTTP_HEADER_CONDITIONAL_IF_MATCH,
                                             "").split(',')
            current_etag = self.compute_etag(json.dumps(result))
            for e in etags:
                if e == current_etag or e == '"*"':
                    match = True
                    break

            if not match:
                # If is a PUT operation and the change request state
                # is already reflected in the current state of the
                # target resource it must return 2xx(Succesful)
                # https://tools.ietf.org/html/rfc7232#section-3.1
                if self.request.method == REQUEST_TYPE_UPDATE:
                    data = json.loads(self.request.body)
                    if OVSDB_SCHEMA_CONFIG in data and \
                        data[OVSDB_SCHEMA_CONFIG] == \
                            result[OVSDB_SCHEMA_CONFIG]:
                            # Set PUT Successful code and finish
                            self.set_status(httplib.OK)
                            return False
                # For POST, GET, DELETE, PATCH return precondition failed
                self.set_status(httplib.PRECONDITION_FAILED)
                return False
        # Etag matches
        return True

    @gen.coroutine
    def options(self):

        resource = self.resource_path
        while resource.next is not None:
            resource = resource.next

        allowed_methods = ', '.join(resource.get_allowed_methods(self.schema))

        self.set_header(HTTP_HEADER_ALLOW, allowed_methods)
        self.set_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_METHODS,
                        allowed_methods)

        if HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS in self.request.headers:
            header_ = HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS
            self.set_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS,
                            self.request.headers[header_])

        self.set_status(httplib.OK)
        self.finish()

    @gen.coroutine
    def get(self):

        selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)

        app_log.debug("Query arguments %s" % self.request.query_arguments)

        result = get.get_resource(self.idl, self.resource_path,
                                  self.schema, self.request.path,
                                  selector, self.request.query_arguments)

        if result is None:
            self.set_status(httplib.NOT_FOUND)
        elif self.successful_query(result):
            self.set_status(httplib.OK)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(json.dumps(result))

        self.finish()

    @gen.coroutine
    def post(self):

        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:
            try:
                # get the POST body
                post_data = json.loads(self.request.body)

                # create a new ovsdb transaction
                self.txn = self.ref_object.manager.get_new_transaction()

                # post_resource performs data verficiation, prepares and
                # commits the ovsdb transaction
                result = post.post_resource(post_data, self.resource_path,
                                            self.schema, self.txn,
                                            self.idl)

                status = result.status
                if status == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction
                    # completes with either success or failure
                    yield self.txn.event.wait()
                    status = self.txn.status

                # complete transaction
                self.transaction_complete(status)

            except APIException as e:
                self.on_exception(e)

            except ValueError as e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(utils.to_json_error(e))

            except Exception as e:
                self.on_exception(e)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    @gen.coroutine
    def put(self):
        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:
            try:
                # get the PUT body
                update_data = json.loads(self.request.body)
                # create a new ovsdb transaction
                self.txn = self.ref_object.manager.get_new_transaction()

                # put_resource performs data verfication, prepares and
                # commits the ovsdb transaction
                result = put.put_resource(update_data, self.resource_path,
                                          self.schema, self.txn, self.idl)

                status = result.status
                if status == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction
                    # completes with either success or failure
                    yield self.txn.event.wait()
                    status = self.txn.status

                # complete transaction
                self.transaction_complete(status)

            except APIException as e:
                self.on_exception(e)

            except ValueError as e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(utils.to_json_error(e))

            except Exception as e:
                self.on_exception(e)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    @gen.coroutine
    def delete(self):

        try:
            self.txn = self.ref_object.manager.get_new_transaction()

            result = delete.delete_resource(self.resource_path,
                                            self.schema, self.txn,
                                            self.idl)
            status = result.status
            if status == INCOMPLETE:
                self.ref_object.manager.monitor_transaction(self.txn)
                # on 'incomplete' state we wait until the transaction
                # completes with either success or failure
                yield self.txn.event.wait()
                status = self.txn.status

            # complete transaction
            self.transaction_complete(status)

        except APIException as e:
            self.on_exception(e)

        except Exception as e:
            self.on_exception(e)

        self.finish()

    def transaction_complete(self, status):

        # TODO: The http status codes are currently
        # not in accordance with REST good practices.

        app_log.debug("Transaction result: %s", status)

        method = self.request.method
        if status == SUCCESS:
            if method == 'POST':
                self.set_status(httplib.CREATED)
            elif method == 'PUT':
                self.set_status(httplib.OK)
            elif method == 'DELETE':
                self.set_status(httplib.NO_CONTENT)

        elif status == UNCHANGED:
            self.set_status(httplib.OK)

        else:
            error = self.txn.get_error()
            raise APIException(error)

    def successful_query(self, result):

        if isinstance(result, dict) and ERROR in result:
            self.set_status(httplib.BAD_REQUEST)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(utils.to_json(result))
            return False
        else:
            return True
