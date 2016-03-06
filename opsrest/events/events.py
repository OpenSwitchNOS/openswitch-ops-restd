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

from tornado.log import app_log
from .exceptions import *
from .subscriber import EventSubscriber, get_events_by_table_names

import message as evmsg

_g_manager = None
_g_subscribers = {}


def get_manager():
    global _g_manager
    return _g_manager


def set_manager(manager):
    """
    Sets the OvsdbConnectionManager and registers a method for callback
    to be notified when there are IDL changes.
    """
    global _g_manager

    # If manager was previously set, make sure to remove previous call back
    if _g_manager is not None:
        _g_manager.remove_change_callback(db_changed_notification)

    _g_manager = manager
    _g_manager.add_change_callback(db_changed_notification)


def process_msg(sub_id, event_msg, idl, schema):
    """
    Process incoming event message. Currently only expecting
    subscription messages.

    Returns an event response dictionary.
    """
    errors = None
    subscriber = _g_subscribers[sub_id]

    if evmsg.is_subscription(event_msg):
        sub_data = evmsg.get_subscription_data(event_msg)

        try:
            subscriber.process_subscriptions(sub_data, idl, schema)
        except EventSubscriptionError as e:
            errors = evmsg.create_errors_dict(e.details)
    else:
        errors = ["Unsupported event type"]

    return evmsg.create_response(errors)


def db_changed_notification(idl):
    """
    Callback for being notified of database changes detected. Invoked from
    the OvsdbConnectionManager.
    """
    app_log.debug("DB changes notification received.")
    notifications = {}
    events_for_rows_deleted = []

    for table, events in get_events_by_table_names().iteritems():
        if not _is_table_changed(table, idl):
            app_log.debug("No changes detected for table " + table)
            continue

        app_log.debug("Change for table %s detected." % table)

        # Check all events for this table to see if any meets to trigger
        # notification
        for event in events:
            app_log.debug("Checking for changes for event:\n%s" % event)

            change = None
            details = None

            # If this type of event is only to monitor a row, check
            # for row change
            if event.is_row_type():
                change, details = _get_row_change_type_and_details(table, idl,
                                                                   event)

                if change == evmsg.EVENT_CHANGE_TYPE_DELETED:
                    # If the row is no longer there, no point in tracking
                    # it further. Delete from the subscriber.
                    events_for_rows_deleted.append(event)
            else:
                # Event is for table-wide changes.
                change = evmsg.EVENT_CHANGE_TYPE_UPDATED

            if change:
                app_log.debug("Change type \"%s\" detected." % change)

                # All conditions met. Store notification to send to subscriber.
                notification_dict = evmsg.create_event_notify_dict(event.id,
                                                                   change,
                                                                   details)

                if event.sub_id not in notifications:
                    notifications[event.sub_id] = []

                app_log.debug("Adding notification to message: %s" %
                              notification_dict)
                notifications[event.sub_id].append(notification_dict)

    # Delete any events for rows that were deleted
    for event in events_for_rows_deleted:
        _g_subscribers[event.sub_id].delete_event(event)

    for sub_id, notifications_list in notifications.iteritems():
        notification_data = evmsg.create_notification(notifications_list)
        app_log.debug("Notification message to send: %s" % notification_data)

        # Notify the app registered for the subscriber.
        _g_subscribers[sub_id].notify_event(notification_data)


def _get_row_change_type_and_details(table, idl, event):
    """
    Compares changes from the database against subscribed columns. If any
    columns subscribed are detected as changes, the response will be returned
    along with the change type and the columns with its values.

    Returned change type for the row may be either "deleted" or "updated".
    """
    change = None
    details = None

    row = _get_row_from_idl(table, idl, event.row)

    if not row:
        change = evmsg.EVENT_CHANGE_TYPE_DELETED
    else:
        row_changes_from_idl = _get_row_changes_from_idl(table, idl, event.row)
        app_log.debug("Row changes from idl: %s" %
                      row_changes_from_idl.columns)

        # Get the intersection between subscribed columns and changes detected
        # from the IDL. If fields is empty, then it indicates all columns
        # are registered to, therefore get all changes from the IDL.
        if event.fields:
            subscribed_row_changes = event.fields

            # Identify if there were any changes for the columns subscribed to
            row_changes = row_changes_from_idl.columns & subscribed_row_changes
        else:
            row_changes = row_changes_from_idl.columns

        app_log.debug("Row changes detected: %s" % row_changes)

        if row_changes:
            change = evmsg.EVENT_CHANGE_TYPE_UPDATED

            # TODO: In the future, get the values associated with the columns
            # and send as a part of the message. For now, only set the details
            # as a list of the columns changed
            details = list(row_changes)

    app_log.debug("Row change type: %s, details: %s" % (change, details))
    return change, details


def add_subscriber(sub_id, callback):
    """
    Adds a subscriber and register the callback for DB change notifications.
    """
    if sub_id not in _g_subscribers:
        _g_subscribers[sub_id] = EventSubscriber(sub_id, callback)
    else:
        raise EventSubscriptionError("Invalid subscriber " + sub_id)


def remove_subscriber(sub_id):
    app_log.debug("Deleting subscriber %s" % sub_id)

    if sub_id in _g_subscribers:
        del _g_subscribers[sub_id]


def _get_row_from_idl(table, idl, row_uuid):
    """
    Returns the row object from the IDL using table name and the row UUID.
    """
    row = None

    if table not in idl.tables:
        app_log.info("Invalid table name %s" % table)
    elif row_uuid not in idl.tables[table].rows:
        app_log.info("Row %s does not exist" % row_uuid)
    else:
        row = idl.tables[table].rows[row_uuid]

    return row


def _get_table_changes_from_idl(table, idl):
    """
    Returns the list of changes from the IDL for the given table name.
    """
    return idl.track_get(table)


def _get_row_changes_from_idl(table, idl, row_uuid):
    """
    Returns the list of changes for the row from the IDL for the given
    table name and row UUID.
    """
    table_changes = _get_table_changes_from_idl(table, idl)
    row_changes = None

    if table_changes is None:
        app_log.error("Table was not tracked")
    elif row_uuid in table_changes:
        row_changes = table_changes[row_uuid]

    return row_changes


def _is_table_changed(table, idl):
    return True if _get_table_changes_from_idl(table, idl) else False
