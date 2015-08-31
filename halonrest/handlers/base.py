from tornado.ioloop import IOLoop
from tornado import web, gen, locks

import json
import httplib
import re

from halonrest.resource import Resource
from halonrest.parse import parse_url_path
from halonrest.constants import *
from halonrest.utils.utils import *
from halonrest import get, post, delete

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

        self.resource_path = parse_url_path(self.request.path, self.schema, self.idl, self.request.method)

        if self.resource_path is None:
            self.set_status(httplib.NOT_FOUND)
            self.finish()

    @gen.coroutine
    def get(self):

        result = get.get_resource(self.idl, self.resource_path, self.schema, self.request.path)
        if result is None:
            self.set_status(httplib.NOT_FOUND)
        else:
            self.set_status(httplib.OK)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(json.dumps({'data': result}))

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
                if result is INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)

                    # on 'incomplete' state we wait until the transaction completes with either success or failure
                    yield self.txn.event.wait()

                txn_status = self.txn.status
                self.set_status(httplib.CREATED)
            except ValueError, e:
                self.set_status(httplib.BAD_REQUEST)
                self.write(to_json_error(e))
        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    @gen.coroutine
    def delete(self):

        self.txn = self.ref_object.manager.get_new_transaction()
         # post_resource performs data verficiation, prepares and commits the ovsdb transaction
        result = delete.delete_resource(self.resource_path, self.txn, self.idl)
        if result is INCOMPLETE:
            self.ref_object.manager.monitor_transaction(self.txn)

            # on 'incomplete' state we wait until the transaction completes with either success or failure
            yield self.txn.event.wait()

        txn_status = self.txn.status
        self.set_status(httplib.NO_CONTENT)
        self.finish()
