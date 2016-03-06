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

import json
from .exceptions import *

# Application fields
WS_APPLICATION_DATA = 'data'

# Message types
WS_MSG_TYPE = 'type'
WS_MSG_TYPE_REQUEST = 'request'
WS_MSG_TYPE_RESPONSE = 'response'

# Status
WS_MSG_STATUS = 'status'
WS_MSG_STATUS_SUCCESS = 'successful'
WS_MSG_STATUS_ERROR = 'error'

# Any info related to response
WS_MSG_RESPONSE_INFO = 'info'


def _validate_mandatory_fields(message):
    """
    Validates the mandatory fields of a websocket message. Raises a
    WSInvalidMessage if a field is missing.
    """
    missing_field = None

    if WS_MSG_TYPE not in message:
        missing_field = WS_MSG_TYPE
    elif is_response(message) and WS_MSG_STATUS not in message:
        missing_field = WS_MSG_STATUS
    elif is_request(message) and WS_APPLICATION_DATA not in message:
        missing_field = WS_APPLICATION_DATA
    elif (is_response(message) and is_status_success(message) and
          WS_APPLICATION_DATA not in message):
        missing_field = WS_APPLICATION_DATA

    if missing_field:
        raise WSInvalidMessage("\"%s\" missing from message" %
                               missing_field)


def _validate_values(message):
    """
    Validates the values of the mandatory fields of a websocket message.
    Raises a WSInvalidMessage if an invalid value is encountered.
    """
    error = None

    if not is_request(message) and not is_response(message):
        error = "\"%s\" must be either %s or %s" % (WS_MSG_TYPE,
                                                    WS_MSG_TYPE_REQUEST,
                                                    WS_MSG_TYPE_RESPONSE)
    elif (is_response(message) and not
          is_status_success(message) and not
          is_status_error(message)):
        error = "\"%s\" must be either %s or %s" % (WS_MSG_STATUS,
                                                    WS_MSG_STATUS_SUCCESS,
                                                    WS_MSG_STATUS_ERROR)

    if error:
        raise WSInvalidMessage(error)


def validate(message):
    """
    Validates the websocket message and raises any errors.
    """
    _validate_mandatory_fields(message)
    _validate_values(message)


def is_request(message):
    return message[WS_MSG_TYPE] == WS_MSG_TYPE_REQUEST


def is_response(message):
    return message[WS_MSG_TYPE] == WS_MSG_TYPE_RESPONSE


def is_status_success(message):
    return message[WS_MSG_STATUS] == WS_MSG_STATUS_SUCCESS


def is_status_error(message):
    return message[WS_MSG_STATUS] == WS_MSG_STATUS_ERROR


def get_app_type(message):
    """
    Returns the application type detected in the websocket message.
    """
    app_type = None
    app_data = message[WS_APPLICATION_DATA]

    # There is only one element in the dictionary for app_data. The key
    # is the application type
    if app_data and app_data.keys():
        app_type = app_data.keys()[0]

    return app_type


def get_app_data(message):
    """
    Returns the data portion belonging to the application.
    """
    return message[WS_APPLICATION_DATA]


def _init_message(type, app_type, data):
    message = {}
    message[WS_MSG_TYPE] = type

    if data:
        message[WS_APPLICATION_DATA] = {app_type: data}

    return message


def create_response(status, app_type, data, info=""):
    """
    Creates a message for response. The returned data is a JSON string
    of the response message.
    """
    response = _init_message(WS_MSG_TYPE_RESPONSE, app_type, data)
    response[WS_MSG_STATUS] = status

    if status != WS_MSG_STATUS_SUCCESS:
        response[WS_MSG_RESPONSE_INFO] = info

    validate(response)
    return json.dumps(response)


def create_request(app_type, data):
    """
    Creates a message for request. The returned data is a JSON string
    of the request message.
    """
    request = _init_message(WS_MSG_TYPE_REQUEST, app_type, data)

    validate(request)
    return json.dumps(request)
