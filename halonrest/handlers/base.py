from tornado.ioloop import IOLoop
from tornado import web, gen, locks
from tornado.log import app_log

import json
import httplib
import re

from halonrest.resource import Resource
from halonrest.parse import parse_url_path
from halonrest.constants import *
from halonrest.utils.utils import *
from halonrest import get, post, delete, put

class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl
        self.request.path = re.sub("/{2,}", "/", self.request.path)

        # CORS
        allow_origin = self.request.protocol + "://"
        allow_origin += self.request.host.split(":")[0] # removing port if present
        self.set_header("Access-Control-Allow-Origin", allow_origin)
        self.set_header("Access-Control-Expose-Headers", "Date")

        # TODO - remove next line before release - needed for testing
        self.set_header("Access-Control-Allow-Origin", "*")

class AutoHandler(BaseHandler):

    # parse the url and http params.
    def prepare(self):

        app_log.debug("Processing request from client: %s" % self.request.remote_ip)
        app_log.debug("Request received: %s" % self.request)

        self.resource_path = parse_url_path(self.request.path, self.schema, self.idl, self.request.method)

        if self.resource_path is None:
            app_log.debug("Invalid URL! Cannot process blank URL")
            self.set_status(httplib.NOT_FOUND)
            self.finish()

    def on_finish(self):
        app_log.debug("Request from client %s processed!" % self.request.remote_ip)

    @gen.coroutine
    def get(self):

        selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)

        result = get.get_resource(self.idl, self.resource_path, self.schema, self.request.path, selector)

        if result is None:
            app_log.debug("Invalid URL! Requested URL does not exist.")
            self.set_status(httplib.NOT_FOUND)
        else:
            app_log.debug("Valid URL! Requested URL found.")
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

                # post_resource performs data verficiation, prepares and commits the ovsdb transaction
                result = post.post_resource(post_data, self.resource_path, self.schema, self.txn, self.idl)
                app_log.debug("Request validation result: %s" % result)

                if result == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction completes with either success or failure
                    yield self.txn.event.wait()
                    result = self.txn.status

                if self.successful_transaction(result):
                    app_log.debug("Successful transaction!")
                    self.set_status(httplib.CREATED)

            except ValueError, e:
                app_log.debug("Exception caught! %s" % e)
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
                self.write(to_json_error(e))

            # TODO: Improve exception handler
            except Exception, e:
                app_log.debug("Caught unknown exception! %s" % e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)

        else:
            app_log.debug("No HTTP_HEADER_CONTENT_LENGTH found! Aborting.")
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

                # put_resource performs data verficiation, prepares and commits the ovsdb transaction
                result = put.put_resource(update_data, self.resource_path, self.schema, self.txn, self.idl)

                if result == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction completes with either success or failure
                    yield self.txn.event.wait()
                    result = self.txn.status

                if self.successful_transaction(result):
                    app_log.debug("Successful transaction!")
                    self.set_status(httplib.OK)

            except ValueError, e:
                app_log.debug("Exception caught! %s" % e)
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
                self.write(to_json_error(e))

            # TODO: Improve exception handler
            except Exception, e:
                app_log.debug("Caught unknown exception! %s" % e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)

        else:
            app_log.debug("No HTTP_HEADER_CONTENT_LENGTH found! Aborting.")
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    @gen.coroutine
    def delete(self):

        self.txn = self.ref_object.manager.get_new_transaction()

        result = delete.delete_resource(self.resource_path, self.schema, self.txn, self.idl)

        if result == INCOMPLETE:
            self.ref_object.manager.monitor_transaction(self.txn)
            # on 'incomplete' state we wait until the transaction completes with either success or failure
            yield self.txn.event.wait()
            result = self.txn.status

        if self.successful_transaction(result):
            app_log.debug("Successful transaction!")
            self.set_status(httplib.NO_CONTENT)

        self.finish()

    def successful_transaction(self, result):

        if result == SUCCESS or result == UNCHANGED:
            return True

        app_log.debug("Transaction failed!")
        self.txn.abort()

        if result == ERROR:
            self.set_status(httplib.BAD_REQUEST)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(to_json_error(self.txn.get_db_error_msg()))

        elif ERROR in result:
            self.set_status(httplib.BAD_REQUEST)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(to_json(result))

        else:
            self.set_status(httplib.INTERNAL_SERVER_ERROR)

        return False
