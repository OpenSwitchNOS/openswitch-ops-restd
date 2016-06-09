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

from opsrest.constants import *
from opsrest.utils import utils
from opsrest.utils import getutils
from opsrest import verify
from opsrest.exceptions import (
    InternalError,
    TransactionFailed
)

import httplib
import types

from tornado.log import app_log
from tornado import gen

@gen.coroutine
def get_resource(idl, resource, schema, uri=None,
                 selector=None, query_arguments=None,
                 fetch_readonly=False):

    depth = getutils.get_depth_param(query_arguments)

    if isinstance(depth, dict) and ERROR in depth:
        return depth

    if resource is None:
        return None

    # We want to get System table
    if resource.next is None:
        resource_query = resource
    else:
        while True:
            if resource.next.next is None:
                break
            resource = resource.next
        resource_query = resource.next

    utils.update_resource_keys(resource_query, schema, idl)

    if verify.verify_http_method(resource, schema, "GET") is False:
        raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

    # GET on System table
    if resource.next is None:
        if query_arguments is not None:
            validation_result = \
                getutils.validate_non_plural_query_args(query_arguments)

            if ERROR in validation_result:
                return validation_result

        # Fetch all read-only columns prior to retrieving row data
        if fetch_readonly:
            row = idl.tables[resource.table].rows[resource.row]
            utils.fetch_readonly_columns(schema, resource.table, idl, [row])

        return get_row_json(resource.row, resource.table, schema,
                            idl, uri, selector, depth,
                            fetch_readonly=fetch_readonly)
    else:
        # Other tables
        return get_resource_from_db(resource, schema, idl, uri,
                                    selector, query_arguments, depth,
                                    fetch_readonly)


# get resource from db using resource->next_resource pair
def get_resource_from_db(resource, schema, idl, uri=None,
                         selector=None, query_arguments=None,
                         depth=0, fetch_readonly=False):

    resource_result = None
    uri = _get_uri(resource, schema, uri)

    # Determine if result will be a collection or a single
    # resource, plus the table to use in post processing
    is_collection = is_resource_type_collection(resource)
    table = resource.next.table

    sorting_args = []
    filter_args = {}
    pagination_args = {}
    keys_args = []
    offset = None
    limit = None

    validation_result = getutils.validate_query_args(sorting_args, filter_args,
                                                     pagination_args,
                                                     keys_args,
                                                     query_arguments,
                                                     schema, resource.next,
                                                     depth, is_collection)
    if ERROR in validation_result:
        return validation_result

    if REST_QUERY_PARAM_OFFSET in pagination_args:
        offset = pagination_args[REST_QUERY_PARAM_OFFSET]
    if REST_QUERY_PARAM_LIMIT in pagination_args:
        limit = pagination_args[REST_QUERY_PARAM_LIMIT]

    app_log.debug("Sorting args: %s" % sorting_args)
    app_log.debug("Filter args: %s" % filter_args)
    app_log.debug("Limit % s" % limit)
    app_log.debug("Offset % s" % offset)
    app_log.debug("Keys % s" % keys_args)

    # Get the resource result according to result type
    if is_collection:
        resource_result = get_collection_json(resource, schema, idl, uri,
                                              selector, depth, fetch_readonly)
    else:
        # Fetch all read-only columns prior to retrieving row data
        if fetch_readonly:
            row = idl.tables[resource.next.table].rows[resource.next.row]
            utils.fetch_readonly_columns(schema, resource.next.table, idl,
                                         [row])

        resource_result = get_row_json(resource.next.row, resource.next.table,
                                       schema, idl, uri, selector, depth,
                                       fetch_readonly=fetch_readonly)

    # Post process data if it necessary
    if (resource_result and depth and isinstance(resource_result, list)):
        # Apply filters, sorting, and pagination
        resource_result = getutils.post_process_get_data(resource_result,
                                                         sorting_args,
                                                         filter_args, offset,
                                                         limit, keys_args,
                                                         schema, table,
                                                         categorized=True)

    return resource_result


def get_collection_json(resource, schema, idl, uri, selector, depth,
                        fetch_readonly=False):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        resource_result = get_table_json(resource.next.table, schema, idl, uri,
                                         selector, depth, fetch_readonly)

    elif resource.relation is OVSDB_SCHEMA_CHILD:
        resource_result = get_column_json(resource.column, resource.row,
                                          resource.table, schema, idl, uri,
                                          selector, depth,
                                          fetch_readonly=fetch_readonly)

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        resource_result = get_back_references_json(resource.row,
                                                   resource.table,
                                                   resource.next.table, schema,
                                                   idl, uri, selector, depth,
                                                   fetch_readonly)

    return resource_result


def get_row_json(row, table, schema, idl, uri, selector=None,
                 depth=0, depth_counter=0, with_empty_values=False,
                 fetch_readonly=False):

    depth_counter += 1
    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    table_schema = schema.ovs_tables[table]

    keys = {}
    keys[OVSDB_SCHEMA_CONFIG] = table_schema.config
    keys[OVSDB_SCHEMA_STATS] = table_schema.stats
    keys[OVSDB_SCHEMA_STATUS] = table_schema.status
    keys[OVSDB_SCHEMA_REFERENCE] = table_schema.references

    if table_schema.dynamic:
        keys = utils.update_category_keys(keys, db_row,
                                          idl, schema,
                                          table)

    config_keys = {}
    config_data = {}
    if selector is None or selector == OVSDB_SCHEMA_CONFIG:
        config_keys = keys[OVSDB_SCHEMA_CONFIG]
        config_data = utils.row_to_json(db_row, config_keys)

    # To remove the unnecessary empty values from the config data
    if not with_empty_values:
        config_data = {key: config_data[key] for key in config_keys
                       if not getutils.is_empty_value(config_data[key])}

    stats_keys = {}
    stats_data = {}
    if selector is None or selector == OVSDB_SCHEMA_STATS:
        stats_keys = keys[OVSDB_SCHEMA_STATS]
        stats_data = utils.row_to_json(db_row, stats_keys)

    # To remove all the empty columns from the satistics data
    if not with_empty_values:
        stats_data = {key: stats_data[key] for key in stats_keys
                      if not getutils.is_empty_value(stats_data[key])}

    status_keys = {}
    status_data = {}
    if selector is None or selector == OVSDB_SCHEMA_STATUS:
        status_keys = keys[OVSDB_SCHEMA_STATUS]
        status_data = utils.row_to_json(db_row, status_keys)

    # To remove all the empty columns from the status data
    if not with_empty_values:
        status_data = {key: status_data[key] for key in status_keys
                       if not getutils.is_empty_value(status_data[key])}

    # Categorize references
    references = keys[OVSDB_SCHEMA_REFERENCE]
    reference_data = []
    for key in references:
        # Ignore parent column in case of back references as we
        # already are in the child table whose row we need to fetch
        if references[key].ref_table == table_schema.parent:
            continue

        if (depth_counter >= depth):
            depth = 0

        temp = get_column_json(key, row, table, schema,
                               idl, uri, selector, depth,
                               depth_counter, fetch_readonly)

        # The condition below is used to discard the empty list of references
        # in the data returned for get requests
        if not temp:
            continue

        reference_data = temp

        # Depending upon the category of the
        # reference pair them with the right data set
        category = references[key].category

        if category == OVSDB_SCHEMA_CONFIG:
            config_data.update({key: reference_data})

        elif category == OVSDB_SCHEMA_STATUS:
            status_data.update({key: reference_data})

        elif category == OVSDB_SCHEMA_STATS:
            stats_data.update({key: reference_data})

    # Categorize by selector
    data = getutils._categorize_by_selector(config_data, stats_data,
                                            status_data, selector)

    return data


# get list of all table row entries
def get_table_json(table, schema, idl, uri, selector=None, depth=0,
                   fetch_readonly=False):

    db_table = idl.tables[table]

    resources_list = []

    if not depth:
        for row in db_table.rows.itervalues():
            tmp = utils.get_table_key(row, table, schema, idl)
            _uri = _create_uri(uri, tmp)
            resources_list.append(_uri)
    else:
        # Fetch all read-only columns prior to retrieving row data
        if fetch_readonly:
            utils.fetch_readonly_columns(schema, table, idl,
                                         db_table.rows.itervalues())

        for row in db_table.rows.itervalues():
            json_row = get_row_json(row.uuid, table, schema, idl, uri,
                                    selector, depth,
                                    fetch_readonly=fetch_readonly)
            resources_list.append(json_row)

    return resources_list


def get_column_json(column, row, table, schema, idl, uri,
                    selector=None, depth=0, depth_counter=0,
                    fetch_readonly=False):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    db_col = db_row.__getattr__(column)
    current_table = schema.ovs_tables[table]
    _kv_type = current_table.references[column].kv_type
    # Reference Column
    col_table = current_table.references[column].ref_table
    column_table = schema.ovs_tables[col_table]

    if _kv_type:
        resources_list = {}
    else:
        resources_list = []
    # GET without depth
    if not depth:
        # Is a top level table
        if column_table.parent is None:
            uri = _get_base_uri() + column_table.plural_name
        # Is a child table, is faster concatenate the uri instead searching
        elif column_table.parent == current_table.name:
            # If this is a child reference URI don't add the column path.
            if column_table.plural_name not in uri:
                uri = uri.rstrip('/')
                uri += '/' + column_table.plural_name

        if _kv_type:
            key_type = current_table.references[column].kv_key_type.name
            for k, v in db_col.iteritems():
                # Reference with different parent, search the parent
                if column_table.parent is not None and \
                        column_table.parent != current_table.name:
                    uri = _get_base_uri()
                    uri += utils.get_reference_parent_uri(col_table, v,
                                                          schema, idl)
                    uri += column_table.plural_name

                # Set URI for key
                tmp = utils.get_table_key(v, column_table.name, schema, idl)
                # TODO: Support other types
                if key_type == INTEGER:
                    k = str(k)
                _uri = _create_uri(uri, tmp)
                resources_list.update({k: _uri})

        else:
            for value in db_col:
                # Reference with different parent, search the parent
                if column_table.parent is not None and \
                        column_table.parent != current_table.name:
                    uri = _get_base_uri()
                    uri += utils.get_reference_parent_uri(col_table, value,
                                                          schema, idl)
                    uri += column_table.plural_name

                # Set URI for key
                tmp = utils.get_table_key(value, column_table.name, schema, idl)
                _uri = _create_uri(uri, tmp)

                resources_list.append(_uri)
    # GET with depth
    else:
        ref_rows = []
        if _kv_type:
            ref_rows = db_col.values()
            ref_keys = db_col.keys()
        else:
            ref_rows = db_col

        # Fetch all read-only columns prior to retrieving row data
        if fetch_readonly:
            utils.fetch_readonly_columns(schema, table, idl, ref_rows)
        i = 0
        for ref_row in ref_rows:
            json_row = get_row_json(ref_row.uuid, col_table, schema, idl, uri,
                                    selector, depth, depth_counter,
                                    fetch_readonly=fetch_readonly)
            if _kv_type:
                resources_list.update({ref_keys[i]: json_row})
            else:
                resources_list.append(json_row)
            i= i+1

    return resources_list


def _get_referenced_row(schema, table, row, column, column_row, idl):

    table_schema = schema.ovs_tables[table]

    # Set correct row for kv_type references
    if table_schema.references[column].kv_type:
        db_table = idl.tables[table]
        db_row = db_table.rows[row]
        db_col = db_row.__getattr__(column)
        return db_col[column_row]
    else:
        return column_row


def get_back_references_json(parent_row, parent_table, table,
                             schema, idl, uri, selector=None,
                             depth=0, fetch_readonly=False):

    references = schema.ovs_tables[table].references
    _refCol = None
    for key, value in references.iteritems():
        if (value.relation == OVSDB_SCHEMA_PARENT and
                value.ref_table == parent_table):
            _refCol = key
            break

    if _refCol is None:
        return None

    resources_list = []

    if not depth:
        for row in idl.tables[table].rows.itervalues():
            ref = row.__getattr__(_refCol)
            if ref.uuid == parent_row:
                tmp = utils.get_table_key(row, table, schema, idl, False)
                _uri = _create_uri(uri, tmp)
                resources_list.append(_uri)
    else:
        # Fetch all read-only columns prior to retrieving row data
        rows = []
        for row in idl.tables[table].rows.itervalues():
            ref = row.__getattr__(_refCol)
            if ref.uuid == parent_row:
                rows.append(row)

        if fetch_readonly:
            utils.fetch_readonly_columns(schema, table, idl, rows)

        for row in rows:
            json_row = get_row_json(row.uuid, table, schema, idl, uri,
                                    selector, depth,
                                    fetch_readonly=fetch_readonly)
            resources_list.append(json_row)

    return resources_list


def _get_base_uri():
    return OVSDB_BASE_URI


def _get_uri(resource, schema, uri=None):
    '''
    returns the right URI based on the category of the
    table.
    e.g. top-level table such as port have /system/ports as URI
    '''
    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            uri = _get_base_uri() + \
                schema.ovs_tables[resource.next.table].plural_name

    return uri


def _create_uri(uri, paths):
    '''
    Removes trailing '/' characters,
    in order to not repeat it when joining it with
    other path.
    Example /system/ports/ -> /system/ports
    '''
    if not uri.endswith('/'):
        uri += '/'
    uri += '/'.join(paths)
    return uri


def is_resource_type_collection(resource):

    is_collection = False

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            is_collection = True

    elif resource.relation is OVSDB_SCHEMA_CHILD:
        if resource.next.row is None:
            is_collection = True

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        if isinstance(resource.next.row, types.ListType):
            is_collection = True

    return is_collection
