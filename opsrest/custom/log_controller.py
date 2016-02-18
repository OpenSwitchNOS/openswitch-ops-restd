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
from opsrest.exceptions import *
from opsrest.constants import *

LOGS_OPTIONS = "options"
LOGS_MATCHES = "matches"
LOGS_PAGINATION = "pagination"
JOURNALCTL_CMD = "journalctl"
OUTPUT_FORMAT = "--output=json-pretty"

class LogController(BaseController):
    FILTER_KEYWORDS = {LOGS_OPTIONS: ["priority", "since", "until",
            "cursor","after_cursor"], LOGS_MATCHES: ["MESSAGE", "MESSAGE_ID", \
            "PRIORITY", "_PID", "_UID", "_GID", "_EXE", "_COMM", \
            "SYSLOG_IDENTIFIER"], LOGS_PAGINATION: ["offset", "limit"]}

    def __init_(self):
        self.base_uri_path = "logs"

    def validate_keywords(self, query_args):
        error_fields = []
        if query_args:
            for k, v in query_args.iteritems():
                if not(k in self.FILTER_KEYWORDS[LOGS_PAGINATION] or
                       k in self.FILTER_KEYWORDS[LOGS_OPTIONS] or
                       k in self.FILTER_KEYWORDS[LOGS_MATCHES]):
                    error_fields.append(k)

        if error_fields:
            raise DataValidationFailed("Invalid log filters %s" % error_fields)

    def get_log_cmd_options(self, query_args):
        log_cmd_options = [JOURNALCTL_CMD]
        if query_args:
            for k,v in query_args.iteritems():
                if k not in self.FILTER_KEYWORDS[LOGS_PAGINATION]:
                    if k in self.FILTER_KEYWORDS[LOGS_MATCHES]:
                        log_cmd_options.append(str(k) + "=" + str(v[0]))
                    else:
                        log_cmd_options.append("--" + str(k) + "=" + str(v[0]))

        log_cmd_options.append(OUTPUT_FORMAT)

        return log_cmd_options

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
        log_cmd_options = self.get_log_cmd_options(query_args)
        response = {}
        app_log.debug("Calling journalctl")
        try:
            response = subprocess.check_output(log_cmd_options)
        except subprocess.CalledProcessError as c:
            app_log.info("Empty log: %s" % c.output)
            response = {}

        if REST_QUERY_PARAM_OFFSET in query_args and REST_QUERY_PARAM_LIMIT in query_args:
            page_params = self.recalculate_pagination(response,
                    int(query_args[REST_QUERY_PARAM_OFFSET][0]), int(query_args[REST_QUERY_PARAM_LIMIT][0]))
            response = getutils.paginate_get_results(response,
                    page_params[0], page_params[1], log=1)

        return (response)
