#!/usr/bin/python
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

# Third party imports
from tornado.log import app_log
import subprocess
import json
import re

# Local imports
from opsrest.utils import *
from opsrest.custom.base_controller import BaseController
from opsrest.exceptions import DataValidationFailed
from opsrest.constants import *

LOGS_OPTIONS = "options"
LOGS_MATCHES = "matches"
LOGS_PAGINATION = "pagination"
JOURNALCTL_CMD = "journalctl"
OUTPUT_FORMAT = "--output=json"
RECENT_ENTRIES = "-n1000"


class LogController(BaseController):
    FILTER_KEYWORDS = {LOGS_OPTIONS: ["priority", "since", "until",
                       "cursor", "after_cursor"], LOGS_MATCHES: ["MESSAGE",
                       "MESSAGE_ID", "PRIORITY", "_PID", "_UID", "_GID",
                       "_EXE", "_COMM", "SYSLOG_IDENTIFIER"],
                       LOGS_PAGINATION: ["offset", "limit"]}

    def __init_(self):
        self.base_uri_path = "logs"

    # This function is to validate the invalid keywords that can be used
    # to use different features of the log api
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

    @staticmethod
    def validation_since_until(arg, error_messages, time_keywords,
                               time_quick_keywords):
        since_until_arg = arg.split(" ", 1)
        if not(since_until_arg[0] in time_quick_keywords):
            if len(since_until_arg) == 2:
                if not((since_until_arg[1] in time_keywords and
                       (since_until_arg[0].isdigit())) or
                       (re.search(r'\d\d\d\d-\d\d-\d\d \d\d:\d:\d\d',
                       since_until_arg[0]) is not None)):
                    error_messages.append("Invalid timestamp value used" +
                                          " % s" % arg)
            else:
                error_messages.append("Incorrect timestamp value" +
                                      " % s" % since_until_arg[0])

        return error_messages

    # This function is to validate the correctness or range of the data that
    # the user wishes to use for different options or features of the log api
    def validate_args_data(self, query_args):
        error_messages = []
        time_quick_keywords = ["yesterday", "now", "today"]
        time_keywords = ["day ago", "days ago", "minute ago", "minutes ago",
                         "hour ago", "hours ago"]

        offset = getutils.get_query_arg("offset", query_args)
        limit = getutils.get_query_arg("limit", query_args)
        if offset is not None and limit is not None:
            if not(offset.isdigit() and limit.isdigit()):
                error_messages.append("Only integers are allowed for offset" +
                                      "and limit")

        priority = getutils.get_query_arg("priority", query_args)
        if priority is not None:
            if int(priority) > 7:
                error_messages.append("Invalid log level. Priority should be" +
                                      "less than or equalto 7: % s" % priority)

        priority_match = getutils.get_query_arg("PRIORITY", query_args)
        if priority_match is not None:
            if int(priority_match) > 7:
                error_messages.append("Invalid log level. Priority should be" +
                                      "less than or equalto 7: % s" %
                                      priority_match)

        since_arg = getutils.get_query_arg("since", query_args)
        if since_arg is not None:
            error_messages = self.validation_since_until(since_arg,
                                                         error_messages,
                                                         time_keywords,
                                                         time_quick_keywords)

        until_arg = getutils.get_query_arg("until", query_args)
        if until_arg is not None:
            error_messages = self.validation_since_until(until_arg,
                                                         error_messages,
                                                         time_keywords,
                                                         time_quick_keywords)

        syslog_identifier_arg = getutils.get_query_arg("SYSLOG_IDENTIFIER",
                                                       query_args)
        if syslog_identifier_arg is not None:
            if re.search(r'\d', str(syslog_identifier_arg)):
                error_messages.append("Daemon name % s can only contain" +
                                      "string literals" %
                                      syslog_identifier_arg)

        if error_messages:
            raise DataValidationFailed("Incorrect data for arguments: %s" %
                                       error_messages)

    # This function is used to aggregate the different options from the uri
    # and form a journalctl command to be executed to get the logs
    # desired by the user
    def get_log_cmd_options(self, query_args):
        log_cmd_options = [JOURNALCTL_CMD]
        if query_args:
            for k, v in query_args.iteritems():
                if k not in self.FILTER_KEYWORDS[LOGS_PAGINATION]:
                    if k in self.FILTER_KEYWORDS[LOGS_MATCHES]:
                        log_cmd_options.append(str(k) + "=" + str(v[0]))
                    else:
                        log_cmd_options.append("--" + str(k) + "=" + str(v[0]))
        else:
            log_cmd_options.append(RECENT_ENTRIES)

        log_cmd_options.append(OUTPUT_FORMAT)

        return log_cmd_options

    # This function is used to convert the response from string to list
    @staticmethod
    def create_response_list(response):
        index_list = []
        index_list = [i.span()[0] for i in re.finditer('{', response)]
        index_list.append(len(response))
        response_list = []

        for i in range(len(index_list) - 1):
            response_list.append(json.loads
                                 (response[index_list[i]:index_list[i+1]]))

        return response_list

    def get_all(self, current_user, selector=None, query_args=None):
        self.validate_keywords(query_args)
        self.validate_args_data(query_args)
        log_cmd_options = self.get_log_cmd_options(query_args)
        response = {}
        app_log.debug("Calling journalctl")
        try:
            response = subprocess.check_output(log_cmd_options)
        except subprocess.CalledProcessError as c:
            app_log.info("Empty log: %s" % c.output)
            response = {}

        if response:
            if REST_QUERY_PARAM_OFFSET in query_args and \
                    REST_QUERY_PARAM_LIMIT in query_args:
                offset = int(query_args[REST_QUERY_PARAM_OFFSET][0])
                limit = int(query_args[REST_QUERY_PARAM_LIMIT][0])
                response = self.create_response_list(response)
                response = getutils.paginate_get_results(response,
                                                         offset,
                                                         limit)
        else:
            response = {"Empty logs": "No logs present for the combination" +
                        "of arguments selected"}

        return (response)
