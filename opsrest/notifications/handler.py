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
from opsrest import parse
from opsrest.get import is_resource_type_collection
from opsrest.utils import utils
from opsrest.constants import OVSDB_SCHEMA_BACK_REFERENCE, OVSDB_BASE_URI
from opsrest.handlers.websocket.notifications import WSNotificationsHandler
from . import utils as notifutils
from . import constants as consts
from .subscription import RowSubscription, CollectionSubscription
from .exceptions import SubscriptionInvalidResource, NotificationException
from .monitor import OvsdbNotificationMonitor
from .utils import lookup_subscriber_by_name


class NotificationHandler():
    def __init__(self, schema, manager):
        self._subscriptions_by_table = {}
        self._subscriptions_by_name = {}
        self._schema = schema

        # Register for callbacks for subscription changes
        self._manager = manager
        manager.add_change_callback(self.subscription_changes_check_callback)

        # Enable monitoring for the subscription table
        self._manager.idl.track_add_all_columns(consts.SUBSCRIPTION_TABLE)

        # Register for callbacks for notifications of subscribed changes
        self._notification_monitor = \
            OvsdbNotificationMonitor(manager.remote,
                                     manager.schema,
                                     self.subscribed_changes_callback)

    def create_subscription(self, subscription_name, subscription_row,
                            resource_uri, idl):
        app_log.debug("Creating subscription for %s with URI %s" %
                      (subscription_name, resource_uri))

        resource = parse.parse_url_path(resource_uri, self._schema, idl)

        # Needs to be at least a top-level resource
        if resource is None or resource.next is None:
            raise SubscriptionInvalidResource("Invalid resource URI " +
                                              resource_uri)

        # Get the subscription's URI
        subscriber_ref_col = \
            utils.get_parent_column_ref(consts.SUBSCRIBER_TABLE,
                                        consts.SUBSCRIPTION_TABLE,
                                        self._schema)
        subscriber = utils.get_parent_row(consts.SUBSCRIBER_TABLE,
                                          subscription_row, subscriber_ref_col,
                                          self._schema, idl)

        sub_parent_uri = OVSDB_BASE_URI
        sub_parent_uri += utils.get_reference_parent_uri(subscription_row)

        subscription_table = self._schema.ovs_tables[consts.SUBSCRIPTION_TABLE]
        subscription_uri = sub_parent_uri + subscription_table.plural_name
        subscription_uri += '/' + utils.row_to_index(subscription_row,
                                                     consts.SUBSCRIPTION_TABLE,
                                                     self._schema, idl,
                                                     subscriber)

        # Get the last resource while preserving the parent resource.
        parent_resource = None
        while resource.next is not None:
            parent_resource = resource
            resource = resource.next

        subscriber_name = self._get_subscriber_name(subscriber, idl)

        subscription = None
        if is_resource_type_collection(resource):
            if resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
                rows = resource.row
            else:
                # TODO: Check returned values
                rows = utils.get_column_data_from_resource(parent_resource,
                                                           idl)

            subscription = CollectionSubscription(resource.table,
                                                  subscriber_name,
                                                  subscription_uri,
                                                  resource_uri, rows)
        else:
            subscription = RowSubscription(resource.table, subscriber_name,
                                           subscription_uri, resource_uri,
                                           resource.row)

        return subscription

    def subscription_changes_check_callback(self, manager, idl):
        """
        Callback method invoked by manager of the IDL used for detecting
        notification subscription changes.
        """
        table_changes = \
            notifutils.get_table_changes_from_idl(consts.SUBSCRIPTION_TABLE,
                                                  idl)

        for sub_uuid, sub_changes in table_changes.iteritems():
            subscription_row = \
                idl.tables[consts.SUBSCRIPTION_TABLE].rows[sub_uuid]

            subscription_name = utils.get_table_key(subscription_row,
                                                    consts.SUBSCRIPTION_TABLE,
                                                    self._schema,
                                                    idl)

            # Only one key, so grab the first index
            subscription_name = subscription_name[0]

            app_log.debug("Subscription changes detected for: \"%s.\"" %
                          subscription_name)

            if notifutils.is_resource_added(sub_changes, idl):
                app_log.debug("Subscription was added.")
                resource_uri = \
                    utils.get_column_data_from_row(subscription_row,
                                                   consts.SUBSCRIPTION_URI)

                try:
                    subscription = self.create_subscription(subscription_name,
                                                            subscription_row,
                                                            resource_uri,
                                                            self._schema, idl)

                    self.add_subscription(subscription_name, subscription)
                except Exception as e:
                    app_log.error("Error while creating subscription: %s" % e)

            elif notifutils.is_resource_deleted(sub_changes, idl):
                app_log.debug("Subscription was deleted.")
                self.remove_subscription(subscription_name)

    def subscribed_changes_callback(self, manager, idl):
        subscriber_notifications = {}

        for table, subscriptions in self._subscriptions_by_table.iteritems():
            if not notifutils.is_table_changed(table, idl):
                continue

            for subscription in subscriptions:
                subs_name = subscription.subscriber_name
                if subs_name not in subscriber_notifications:
                    subscriber_notifications[subs_name] = {}

                try:
                    sub = subscriber_notifications[subs_name]
                    added, modified, deleted = \
                        subscription.get_changes(idl, self._schema)

                    self._add_updates(sub, consts.UPDATE_TYPE_ADDED, added)
                    self._add_updates(sub, consts.UPDATE_TYPE_MODIFIED,
                                      modified)
                    self._add_updates(sub, consts.UPDATE_TYPE_DELETED, deleted)
                except NotificationException as e:
                    app_log.error("Error processing notification."
                                  "Error: %s" % e.details)

        for subscriber_name, changes in subscriber_notifications.iteritems():
            self.notify_subscriber(subscriber_name, changes, idl)

    def notify_subscriber(self, subscriber_name, changes, idl):
        app_log.debug("Notifying subscriber %s." % subscriber_name)
        subscriber_row = lookup_subscriber_by_name(idl, subscriber_name)

        if subscriber_row:
            subscriber_type = self._get_subscriber_type(subscriber_row, idl)

            if subscriber_type == consts.SUBSCRIBER_TYPE_WS:
                WSNotificationsHandler.send_notification_msg(subscriber_name,
                                                             changes)
            else:
                app_log.error("Unsupported subscriber type: %s" %
                              subscriber_type)

    def add_subscription(self, subscription_name, subscription):
        # If the table is not already monitored in the IDL, need to
        # begin monitoring it.
        if subscription.table not in self._subscriptions_by_table:
            self._subscriptions_by_table[subscription.table] = set([])
            self._notification_monitor.add_table_monitor(subscription.table)

        self._subscriptions_by_table[subscription.table].add(subscription)

        # Add the subscription by name for reverse lookup
        self._subscriptions_by_name[subscription_name] = subscription

    def remove_subscription(self, subscription_name):
        subscription = None
        if subscription_name in self._subscriptions_by_name:
            subscription = self._subscriptions_by_name[subscription_name]

            del self._subscriptions_by_name[subscription_name]

        # Remove the subscription from the table map if it exists
        if subscription and subscription.table in self._subscriptions_by_table:
            table = subscription.table
            self._subscriptions_by_table[table].discard(subscription)

            # If the table is no longer being monitored, remove tracking and
            # monitoring from the idl.
            if not self._subscriptions_by_table[table]:
                # No longer need the table entry in the mapping.
                del self._subscriptions_by_table[table]

                # Need to also remove tracking/monitoring
                self._notification_monitor.remove_table_monitor(table)

    def _add_updates(self, subscriber_changes, update_type, updates):
        if not updates:
            return

        if update_type not in subscriber_changes:
            subscriber_changes[update_type] = []

        subscriber_changes[update_type].append(updates)

    def _get_subscriber_type(self, subscriber_row, idl):
        return utils.get_column_data_from_row(subscriber_row,
                                              consts.SUBSCRIBER_TYPE)

    def _get_subscriber_name(self, subscriber_row, idl):
        return utils.get_column_data_from_row(subscriber_row,
                                              consts.SUBSCRIBER_NAME)
