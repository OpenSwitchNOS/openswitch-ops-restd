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

from opsrest import parse
from tornado.log import app_log
from .exceptions import *
import message as evmsg

# Used to maintain events according to table names for faster lookup.
_g_events_by_table = {}


def add_event_by_table_name(table_name, event):
    if table_name not in _g_events_by_table:
        _g_events_by_table[table_name] = set()

    _g_events_by_table[table_name].add(event)


def remove_event_by_table_name(table_name, event):
    if table_name in _g_events_by_table:
        _g_events_by_table[table_name].discard(event)

        if not _g_events_by_table[table_name]:
            del _g_events_by_table[table_name]
    else:
        app_log.info("Table name %s doesn't exist" % table_name)


def get_events_by_table_names():
    return _g_events_by_table


class Event:
    """Stores event data."""
    def __init__(self, id, row, table, fields, sub_id):
        self.id = id
        self.row = row
        self.table = table
        self.fields = set(fields)
        self.sub_id = sub_id

    def is_row_type(self):
        '''Returns bool indicating if this event is subscribed to a row'''
        return self.row is not None

    def __str__(self):
        event_details = "Event-ID: %s\n" % self.id
        event_details += "Row UUID: %s\n" % self.row
        event_details += "Table: %s\n" % self.table
        event_details += "Fields: %s\n" % self.fields
        event_details += "Subscriber: %s\n" % self.sub_id

        return event_details


class EventSubscriber:
    """
    Processes and stores events from subscriptions. Owner of its events.
    Interfaces with the IDL for column tracking.
    """
    def __init__(self, id, callback):
        self.id = id
        self._event_callback = callback
        self._events = {}

    def __del__(self):
        app_log.debug("Removing events from subscriber %s" % self.id)

        for table, events in self._events.iteritems():
            for event in events.values():
                remove_event_by_table_name(event.table, event)

    def process_subscriptions(self, subdata, idl, schema):
        '''
        Process subscription requests from incoming subscription data from
        the client. Each subscription is added as an event upon success.
        '''
        errors = {}
        events = []

        for sub in subdata:
            app_log.debug("Processing subscription data: %s" % sub)

            event_id = evmsg.get_sub_event_id(sub)
            resource_uri = evmsg.get_sub_resource(sub)
            resource_type = evmsg.get_sub_resource_type(sub)
            fields = []

            if resource_type == evmsg.EVENT_RESOURCE_TYPE_ROW:
                fields = evmsg.get_sub_fields(sub)

            try:
                event = self.create_event(event_id, self.id, resource_type,
                                          resource_uri, fields, idl, schema)

                events.append(event)
            except EventSubscriptionError as e:
                app_log.info("Received subscription error: %s" % e.details)

                # Group errors by event id
                if event_id not in errors:
                    errors[event_id] = []

                errors[event_id].append(e.details)

        if errors:
            raise EventSubscriptionError(errors)

        for event in events:
            self.add_event(event, idl)

    def add_event(self, event, idl):
        '''
        Adds the event to the event list.
        '''
        app_log.debug("Adding event:\n%s" % event)

        # Create a new list of events for the table, if it doesn't exist
        if event.table not in self._events:
            self._events[event.table] = {}

        self._events[event.table][event.id] = event
        add_event_by_table_name(event.table, event)

        # Begin tracking in the IDL
        self._begin_event_tracking(event, idl)

    def _begin_event_tracking(self, event, idl):
        '''
        Interface to the IDL for adding the columns to be tracked.
        '''
        if event.fields:
            for column in event.fields:
                idl.track_add_column(event.table, column)
        else:
            idl.track_add_all_columns(event.table)

    def _are_columns_valid(self, table, columns, idl):
        '''
        Returns bool if columns are valid in the IDL.
        '''
        table_columns = idl.tables[table].columns.keys()

        for column in columns:
            if column not in table_columns:
                raise EventInvalidResource("Invalid column " + column)

        return True

    def create_event(self, event_id, sub_id, resource_type,
                     resource_uri, fields, idl, schema):
        '''
        Returns an Event object after performing validations on the
        subscription data in the message.
        '''
        table = None
        row_uuid = None

        if resource_type == evmsg.EVENT_RESOURCE_TYPE_TABLE:
            # For "table" type, the resource_uri is just the table name.
            # No row associated for "table" type. Check if it's a valid table.
            table = resource_uri

            if table not in schema.ovs_tables:
                raise EventInvalidResource("Invalid table name " + table)

        elif resource_type == evmsg.EVENT_RESOURCE_TYPE_ROW:
            resource = parse.parse_url_path(resource_uri, schema, idl)

            # Needs to be at least a top-level resource
            if resource is None or resource.next is None:
                raise EventInvalidResource("Invalid resource URI " +
                                           resource_uri)

            # Get the last resource
            while resource.next is not None:
                resource = resource.next

            table = resource.table
            row_uuid = resource.row

            # Check to ensure it's a valid column to register to. Only for case
            # where not subscribing to all fields and for row type events.
            if fields:
                self._are_columns_valid(table, fields, idl)
        else:
            raise EventInvalidResource("Invalid resource type " +
                                       resource_type)

        if table in self._events and event_id in self._events[table]:
            raise EventSubscriptionError("Duplicate event id %s" % event_id)

        return Event(event_id, row_uuid, table, fields, sub_id)

    def delete_event(self, event):
        remove_event_by_table_name(event.table, event)
        del self._events[event.table][event.id]

    def notify_event(self, notification_data):
        '''
        Notifies registered callback of an event notification.
        '''
        self._event_callback(self.id, notification_data)
