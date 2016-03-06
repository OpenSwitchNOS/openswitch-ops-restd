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

# Event message types
EVENT_SUBSCRIBE = 'subscriptions'
EVENT_NOTIFY = 'notifications'

# Event response
EVENT_RESPONSE_STATUS = 'status'
EVENT_RESPONSE_STATUS_SUCCESS = 'successful'
EVENT_RESPONSE_STATUS_ERROR = 'error'
EVENT_RESPONSE_ERRORS_FIELD = 'errors'
EVENT_RESPONSE_EVENT_ERR_MESSAGES = 'messages'

# Subscription event data
EVENT_SUB_EVENT_ID = 'event_id'
EVENT_SUB_RESOURCE_TYPE = 'type'
EVENT_SUB_RESOURCE = 'resource'
EVENT_SUB_FIELDS = 'fields'

# Resource types to subscribe to. Either table or row.
EVENT_RESOURCE_TYPE_TABLE = 'table'
EVENT_RESOURCE_TYPE_ROW = 'row'

# Notification change types
EVENT_CHANGE_TYPE = 'change'
EVENT_CHANGE_TYPE_UPDATED = 'updated'
EVENT_CHANGE_TYPE_DELETED = 'deleted'

# Event notification field for details
EVENT_NOTIFY_DETAILS = 'details'


def add_response_status(response_msg, status):
    response_msg[EVENT_RESPONSE_STATUS] = status


def add_response_errors(response_msg, errors):
    response_msg[EVENT_RESPONSE_ERRORS_FIELD] = errors


def get_subscription_errors(msg):
    return msg[EVENT_RESPONSE_ERRORS_FIELD]


def is_status_success(msg):
    return msg[EVENT_RESPONSE_STATUS] == EVENT_RESPONSE_STATUS_SUCCESS


def is_status_error(msg):
    return msg[EVENT_RESPONSE_STATUS] == EVENT_RESPONSE_STATUS_ERROR


def is_subscription(event_msg):
    return True if EVENT_SUBSCRIBE in event_msg else False


def is_notification(event_msg):
    return True if EVENT_NOTIFY in event_msg else False


def get_subscription_data(event_msg):
    return event_msg[EVENT_SUBSCRIBE]


def get_notification_data(event_msg):
    return event_msg[EVENT_NOTIFY]


def get_sub_resource(sub_data):
    return sub_data[EVENT_SUB_RESOURCE]


def get_sub_fields(sub_data):
    return sub_data[EVENT_SUB_FIELDS]


def get_sub_resource_type(sub_data):
    return sub_data[EVENT_SUB_RESOURCE_TYPE]


def get_sub_event_id(sub_data):
    return sub_data[EVENT_SUB_EVENT_ID]


def create_response(errors):
    response = {}
    status = EVENT_RESPONSE_STATUS_SUCCESS

    if errors:
        status = EVENT_RESPONSE_STATUS_ERROR
        add_response_errors(response, errors)

    add_response_status(response, status)

    return response


def create_event_subscribe_dict(event_id, type, resource, fields):
    """
    Returns a dictionary for once instance of event subscription.

    Example:
    {
        "event_id": "1",
        "type": "row",
        "resource": "/rest/v1/system/vrfs/vrf_default/bgp_routers/1",
        "fields": ["router_id", "timers"]
    }
    """
    event_dict = {}
    event_dict[EVENT_SUB_EVENT_ID] = event_id
    event_dict[EVENT_SUB_RESOURCE_TYPE] = type
    event_dict[EVENT_SUB_RESOURCE] = resource
    event_dict[EVENT_SUB_FIELDS] = fields

    return event_dict


def create_event_notify_dict(event_id, change_type, details):
    """
    Returns a dictionary for once instance of event subscription.

    Example:
    {
        "event_id": "1",
        "change": "updated",
        "details": [{
            "field": "router_id",
            "value": "2.2.2.2"
        ]
    }
    """
    event_dict = {}
    event_dict[EVENT_SUB_EVENT_ID] = event_id
    event_dict[EVENT_CHANGE_TYPE] = change_type

    if details:
        event_dict[EVENT_NOTIFY_DETAILS] = details

    return event_dict


def create_subscription(subscriptions_list):
    subscription_message = {}
    subscription_message[EVENT_SUBSCRIBE] = subscriptions_list

    return subscription_message


def create_notification(notifications_list):
    notification_message = {}
    notification_message[EVENT_NOTIFY] = notifications_list

    return notification_message


def create_errors_dict(errors_dict):
    errors = []

    for event_id, errors_list in errors_dict.iteritems():
        errors.append({EVENT_SUB_EVENT_ID: event_id,
                       EVENT_RESPONSE_EVENT_ERR_MESSAGES: errors_list})

    return errors
