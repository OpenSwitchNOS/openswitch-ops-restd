#!/usr/bin/python
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

# Third party imports
from tornado.log import app_log
import subprocess
import json
import re
from opsrest.utils import *

# Local imports
from opsrest.custom.base_controller import BaseController

class LogController(BaseController):
    filter_keywords = {"options": ["priority", "since", "until",
            "cursor","after_cursor"], "matches": ["MESSAGE", "MESSAGE_ID", \
            "PRIORITY", "_PID", "_UID", "_GID", "_EXE", "_COMM", \
            "SYSLOG_IDENTIFIER"], "pagination": ["offset", "limit"]}

    def __init_(self):
        self.base_uri_path = "logs"

    def validate_keywords(self, query_args):
        error_fields = []
        if query_args:
            for k, v in query_args.iteritems():
                if k not in self.filter_keywords["pagination"]:
                    if not(k in self.filter_keywords["options"] or
                            k in self.filter_keywords["matches"]):
                        error_fields.append(k)

        if error_fields:
            return ({"error":utils.to_json_error("Invalid log filters: %s" %
                    error_fields)})
        else:
            return False

    def get_log_options(self, query_args):
        log_options = ["journalctl"]
        if query_args:
            for k,v in query_args.iteritems():
                if k not in self.filter_keywords["pagination"]:
                    if k in self.filter_keywords["matches"]:
                        log_options.append(str(k) + "=" + str(v[0]))
                    else:
                        log_options.append("--" + str(k) + "=" + str(v[0]))

        log_options.append("--output=json-pretty")

        return log_options

    def recalculate_pagination(self, response, offset, limit):
        index_list = []
        index_list = [i.span()[0] for i in re.finditer('{', response)]
        index_list.append(len(response))
        index_list_len = len(index_list) - 1

        if offset > index_list_len:
            return [None, None]
        else:
            if (offset + limit) <= index_list_len:
                indx = offset + limit
            else:
                indx = index_list_len
            limit = index_list[indx]
            offset = index_list[offset]

        return [offset, limit]

    def get_all(self, current_user, selector=None, query_args=None):
        error = self.validate_keywords(query_args)
        if error:
            return error

        log_options = self.get_log_options(query_args)
        response = {}
        app_log.debug("Calling journalctl")
        try:
            response = subprocess.check_output(log_options)  #--identifier=dhclient
        except subprocess.CalledProcessError as c:
            app_log.info("Empty log: %s" % c.output)
            response = {}

        if "offset" in query_args and "limit" in query_args:
            page_params = self.recalculate_pagination(response, \
                    int(query_args["offset"][0]), int(query_args["limit"][0]))
            response = getutils.paginate_get_results(response, \
                    page_params[0], page_params[1], log=1)

        return (response)
