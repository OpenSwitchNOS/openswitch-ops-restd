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

import httplib
import json


class APIException(Exception):
    """
    Class to report errors in opsrest.
    """
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]

    def __init__(self, detail=None):
        self.detail = detail

    def __str__(self):
        return json.dumps(self.detail)


class DataValidationFailed(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]


class ParseError(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]


class AuthenticationFailed(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]


class NotAuthenticated(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]


class NotFound(APIException):
    status_code = httplib.NOT_FOUND
    status = httplib.responses[status_code]


class MethodNotAllowed(APIException):
    status_code = httplib.METHOD_NOT_ALLOWED
    status = httplib.responses[status_code]


class PatchOperationFailed(APIException):
    # TODO use proper code, currently httplib
    # doesn't seem to support responses for
    # UNPROCESSABLE_ENTITY, so exception
    # handling breaks
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]
