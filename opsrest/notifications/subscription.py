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

from opsrest.utils.utils import (
    get_reference_parent_uri,
    row_ovs_column_to_json,
    row_to_index
)
from opsrest.get import get_row_json, get_column_json
from .utils import (
    get_table_changes_from_idl,
    is_resource_added,
    is_resource_deleted,
    is_resource_modified
)
from .constants import (
    NOTIF_SUBSCRIPTION_FIELD,
    NOTIF_RESOURCE_FIELD,
    NOTIF_NEW_VALUES_FIELD,
    NOTIF_VALUES_FIELD
)
from .exceptions import NotificationValueError


class Subscription():
    def __init__(self, table, subscriber_name, subscription_uri):
        self.table = table
        self.subscriber_name = subscriber_name
        self.subscription_uri = subscription_uri

    def get_changes(self, idl, schema):
        pass


class RowSubscription(Subscription):
    def __init__(self, table, subscriber_name, subscription_uri,
                 resource_uri, row):
        super(RowSubscription, self).__init__(table, subscriber_name,
                                              subscription_uri)

        # Resource URI as provided in the subscription
        self.resource_uri = resource_uri
        self.row = row

    def get_changes(self, idl, schema):
        deleted = None
        modified = None

        # Check if current subscription is in the list of changes
        table_changes = get_table_changes_from_idl(self.table, idl)
        if self.row in table_changes:
            row_change_info = table_changes[self.row]

            # Check if it was deleted or modified
            if is_resource_modified(row_change_info, idl):
                updated_cols = row_change_info.columns
                columns_to_values = self.get_columns_to_values(self.row,
                                                               updated_cols,
                                                               idl, schema)
                modified = {NOTIF_SUBSCRIPTION_FIELD: self.subscription_uri,
                            NOTIF_RESOURCE_FIELD: self.resource_uri,
                            NOTIF_NEW_VALUES_FIELD: columns_to_values}

            elif is_resource_deleted(row_change_info, idl):
                deleted = {NOTIF_SUBSCRIPTION_FIELD: self.subscription_uri,
                           NOTIF_RESOURCE_FIELD: self.resource_uri}

        return (None, modified, deleted)

    def get_columns_to_values(self, row, columns, idl, schema):
        # Get the OVSColumn from one of the categories: stats, config, status
        # Get the attribute and value_type of the column
        # Convert to json
        # Get the type of the attribute
        # If attribute type or value type is UUID
        #     convert UUID to URI
        column_to_values = {}
        schema_table = schema.ovs_tables[self.table]

        for column in columns:
            data = None

            if column in schema_table.references:
                data = get_column_json(column, row, self.table, schema,
                                       idl, self.resource_uri)
            else:
                ovs_column = None

                if column in schema_table.config:
                    ovs_column = schema_table.config[column]
                elif column in schema_table.stats:
                    ovs_column = schema_table.stats[column]
                elif column in schema_table.status:
                    ovs_column = schema_table.status[column]
                else:
                    raise NotificationValueError("Attribute not found: %s" %
                                                 column)

                    data = row_ovs_column_to_json(row, ovs_column)

            column_to_values[column] = data

        return column_to_values


class CollectionSubscription(Subscription):
    def __init__(self, table, subscriber_name, subscription_uri,
                 collection_uri, rows):
        super(CollectionSubscription, self).__init__(table, subscriber_name,
                                                     subscription_uri)

        # URI to the collection as a list
        self.uri_list = collection_uri.split('/')

        # Rows to be monitored as a part of the collection. Initially
        # populated with the rows currently in the DB.
        self.rows = rows

    def get_changes(self, idl, schema):
        table_changes = get_table_changes_from_idl(self.table, idl)
        added = []
        deleted = []

        for row, row_change_info in table_changes.iteritems():
            # Check for additions
            if is_resource_added(row_change_info, idl):
                # Since added, need to check if it's part of the subscribed
                # collection URI.
                # Get URI trace for this resource.
                parent_uri = get_reference_parent_uri(row)
                uri_trace = parent_uri.split('/')

                # Lengths of the two trace should be the same otherwise don't
                # bother comparing.
                # TODO: Need to confirm the lengths and if this is true
                if len(uri_trace) != len(self.uri_list):
                    break

                for seg1, seg2 in self.uri_segments, uri_trace:
                    # TODO: In the future, for wildcards, also check for *
                    if seg1 != seg2:
                        # This resource change is not a part of a subscribed
                        # collection.
                        break

                # Add new entry
                resource_uri = parent_uri + '/' + row_to_index(row)
                self.rows.update({row: resource_uri})

                # Get all column values for the row and strip it from its
                # category.
                row_values = get_row_json(row, self.table, schema, idl,
                                          resource_uri)
                column_to_values = {}
                for category, values_dict in row_values:
                    row_values.update(values_dict)

                added.append({NOTIF_SUBSCRIPTION_FIELD: self.subscription_uri,
                              NOTIF_RESOURCE_FIELD: resource_uri,
                              NOTIF_VALUES_FIELD: column_to_values})

            elif is_resource_deleted(row_change_info, idl):
                # Check if it's part of a collection that we were tracking
                if row in self.rows:
                    data = {NOTIF_SUBSCRIPTION_FIELD: self.subscription_uri,
                            NOTIF_RESOURCE_FIELD: self.rows[row]}

                    # Grab the resource URI before it's deleted.
                    deleted.append(data)
                    self.rows.remove(row)

        return (added, None, deleted)
