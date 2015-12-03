# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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

import ovs.db.idl
from opsrest.constants import *
from opsrest.utils import utils
from verify import convert_string_to_value_by_type
from opsrest import verify
import httplib
import types
import re
from tornado.log import app_log


def get_resource(idl, resource, schema, uri=None,
                 selector=None, query_arguments=None):

    depth = _get_depth_param(query_arguments)

    if isinstance(depth, dict) and ERROR in depth:
        return depth

    if resource is None:
        return None

    # GET on System table
    if resource.next is None:

        if query_arguments is not None:
            validation_result = validate_non_plural_query_args(query_arguments)

            if ERROR in validation_result:
                return validation_result

        return get_row_json(resource.row, resource.table, schema,
                            idl, uri, selector, depth)

    # All other cases

    # get the last resource pair
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    if verify.verify_http_method(resource, schema, "GET") is False:
        raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

    return get_resource_from_db(resource, schema, idl, uri,
                                selector, query_arguments, depth)


# get resource from db using resource->next_resource pair
def get_resource_from_db(resource, schema, idl, uri=None,
                         selector=None, query_arguments=None,
                         depth=0):

    resource_result = None
    uri = _get_uri(resource, schema, uri)
    table = None

    # Determine if result will be a collection or a single
    # resource, plus the table to use in post processing
    is_collection = _is_result_a_collection(resource)
    table = resource.next.table

    sorting_args = []
    filter_args = {}
    pagination_args = {}
    offset = None
    limit = None

    validation_result = validate_query_args(sorting_args, filter_args,
                                            pagination_args, query_arguments,
                                            resource.next, schema, selector,
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

    # Get the resource result according to result type
    if is_collection:
        resource_result = get_collection_json(resource, schema, idl, uri,
                                              selector, depth)
    else:
        resource_result = get_row_json(resource.next.row, resource.next.table,
                                       schema, idl, uri, selector, depth)

    # Post process data if it necessary
    if (resource_result and depth and isinstance(resource_result, list)):
        # Apply filters, sorting, and pagination
        resource_result = post_process_get_data(resource_result, table, schema,
                                                sorting_args, filter_args,
                                                offset, limit, selector)

    return resource_result


def get_collection_json(resource, schema, idl, uri, selector, depth):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        resource_result = get_table_json(resource.next.table, schema, idl, uri,
                                         selector, depth)

    elif resource.relation is OVSDB_SCHEMA_CHILD:
        resource_result = get_column_json(resource.column, resource.row,
                                          resource.table, schema, idl, uri,
                                          selector, depth)

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        resource_result = get_back_references_json(resource.row,
                                                   resource.table,
                                                   resource.next.table, schema,
                                                   idl, uri, selector, depth)

    return resource_result


def get_null_free_data(row, column_keys, data):
    # In this function we read the row retreived from idl. This data is used
    # to discard the unnecessary empty columns from the data returned for
    # get requests
    get_data = {}
    for c in column_keys:
        attribute = row.__getattr__(c)
        attribute_type = type(attribute)

        # The below condition makes sure that we are not discarding any
        # mandatory column even if it's value is empty
        if column_keys[c].n_min > 0:
            get_data[c] = data[c]
        # The below condition is for optional columns
        elif bool(attribute):
            # Since idl returns all the data as list, dict or unicode, the
            # following if...elif condition is used for approriate filtering
            if attribute_type is list and attribute[0] != '':
                get_data[c] = attribute[0]
            elif attribute_type is dict or attribute_type is unicode:
                get_data[c] = attribute

    return get_data


def get_row_json(row, table, schema, idl, uri, selector=None,
                 depth=0, depth_counter=0):

    depth_counter += 1
    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    print "db_row %s" % db_row
    schema_table = schema.ovs_tables[table]

    config_keys = schema_table.config
    stats_keys = schema_table.stats
    status_keys = schema_table.status
    references = schema_table.references
    reference_keys = references.keys()
    for key in reference_keys:
        if references[key].ref_table == schema_table.parent:
            reference_keys.remove(key)
            break

    config_data = utils.row_to_json(db_row, config_keys)
    # To remove the unnecessary empty values from the config data
    config_data = get_null_free_data(db_row, config_keys, config_data)

    stats_data = utils.row_to_json(db_row, stats_keys)
    # To remove all the empty columns from the satistics data
    stats_data = {key: stats_data[key] for key in stats_keys
                  if stats_data[key]}

    status_data = utils.row_to_json(db_row, status_keys)
    # To remove all the empty columns from the status data
    status_data = {key: status_data[key] for key in status_keys
                   if status_data[key]}

    reference_data = {}
    # get all references
    for key in reference_keys:

        if (depth_counter >= depth):
            depth = 0
        temp = get_column_json(key, row, table, schema,
                               idl, uri, selector, depth,
                               depth_counter)

        # The condition below is used to discard the empty list of references
        # in the data returned for get requests
        if temp:
            reference_data[key] = temp
        else:
            continue

        # TODO Data categorization should be refactored as it
        # is also executed when sorting and filtering results

        # depending upon the category of reference
        # pair them with the right data set
        category = references[key].category
        if category == OVSDB_SCHEMA_CONFIG:
            config_data.update({key: reference_data[key]})
        elif category == OVSDB_SCHEMA_STATUS:
            status_data.update({key: reference_data[key]})
        elif category == OVSDB_SCHEMA_STATS:
            stats_data.update({key: reference_data[key]})

    data = _categorize_by_selector(config_data, stats_data,
                                   status_data, selector)

    return data


# get list of all table row entries
def get_table_json(table, schema, idl, uri, selector=None, depth=0):

    db_table = idl.tables[table]

    resources_list = []

    if not depth:
        for row in db_table.rows.itervalues():
            tmp = utils.get_table_key(row, table, schema, idl)
            _uri = _create_uri(uri, tmp)
            resources_list.append(_uri)
    else:
        for row in db_table.rows.itervalues():
            json_row = get_row_json(row.uuid, table, schema, idl, uri,
                                    selector, depth)
            resources_list.append(json_row)

    return resources_list


def get_column_json(column, row, table, schema, idl, uri,
                    selector=None, depth=0, depth_counter=0):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    db_col = db_row.__getattr__(column)

    current_table = schema.ovs_tables[table]

    # list of resources to return
    resources_list = []

    # Reference Column
    col_table = current_table.references[column].ref_table
    column_table = schema.ovs_tables[col_table]

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

        for value in db_col:

            ref_row = _get_referenced_row(schema, table, row,
                                          column, value, idl)

            # Reference with different parent, search the parent
            if column_table.parent is not None and \
                    column_table.parent != current_table.name:
                uri = _get_base_uri()
                uri += utils.get_reference_parent_uri(col_table, ref_row,
                                                      schema, idl)
                uri += column_table.plural_name

            # Set URI for key
            tmp = utils.get_table_key(ref_row, column_table.name, schema, idl)
            _uri = _create_uri(uri, tmp)

            resources_list.append(_uri)
    # GET with depth
    else:
        for value in db_col:

            ref_row = _get_referenced_row(schema, table, row,
                                          column, value, idl)
            json_row = get_row_json(ref_row.uuid, col_table, schema, idl, uri,
                                    selector, depth, depth_counter)
            resources_list.append(json_row)

    return resources_list


def _get_referenced_row(schema, table, row, column, column_row, idl):

    schema_table = schema.ovs_tables[table]

    # Set correct row for kv_type references
    if schema_table.references[column].kv_type:
        db_table = idl.tables[table]
        db_row = db_table.rows[row]
        db_col = db_row.__getattr__(column)
        return db_col[column_row]
    else:
        return column_row


def get_back_references_json(parent_row, parent_table, table,
                             schema, idl, uri, selector=None,
                             depth=0):

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
                tmp = utils.get_table_key(row, table, schema, idl)
                _uri = _create_uri(uri, tmp)
                resources_list.append(_uri)
    else:
        for row in idl.tables[table].rows.itervalues():
            ref = row.__getattr__(_refCol)
            if ref.uuid == parent_row:
                json_row = get_row_json(row.uuid, _refCol, schema, idl, uri,
                                        selector, depth)
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


def validate_query_args(sorting_args, filter_args, pagination_args,
                        query_arguments, resource, schema, selector,
                        depth, is_collection=True):

    # Non-plural resources only required to validate if
    # sort, filter, or pagination parameters are NOT present
    if not is_collection:
        return validate_non_plural_query_args(query_arguments)

    # For collection resources, go ahead and
    # validate correctness of all parameters

    staging_sort_data = get_sorting_args(query_arguments, resource,
                                         schema, selector)

    # get_sorting_args returns a list of column
    # names to sort by or an ERROR dictionary
    if ERROR in staging_sort_data:
        return staging_sort_data
    else:
        sorting_args.extend(staging_sort_data)

    # get_filters_args returns a dictionary with
    # either filter->value pairs or an ERROR
    filter_args.update(get_filters_args(query_arguments, resource,
                                        schema, selector))

    if ERROR in filter_args:
        return filter_args

    offset = None
    limit = None

    try:
        limit = get_query_arg(REST_QUERY_PARAM_LIMIT, query_arguments)
        offset = get_query_arg(REST_QUERY_PARAM_OFFSET, query_arguments)

        if offset is not None:
            offset = int(offset)

        if limit is not None:
            limit = int(limit)

        pagination_args[REST_QUERY_PARAM_OFFSET] = offset
        pagination_args[REST_QUERY_PARAM_LIMIT] = limit

    except:
        error_json = utils.to_json_error("Pagination indexes must be numbers")
        return {ERROR: error_json}

    if depth == 0 and (sorting_args or filter_args or
                       offset is not None or limit is not None):
        error_json = utils.to_json_error("Sort, filter, and pagination " +
                                         "parameters are only supported " +
                                         "for depth > 0")
        return {ERROR: error_json}

    return {}


def validate_non_plural_query_args(query_arguments):

    error_json = utils.to_json_error("Sort, filter, and pagination " +
                                     "parameters are only supported " +
                                     "for resource collections")
    error_json = {ERROR: error_json}

    # Check if sort or pagination parameters are present

    # NOTE any new query keys should be added to this condition
    if REST_QUERY_PARAM_SORTING in query_arguments or \
            REST_QUERY_PARAM_OFFSET in query_arguments or \
            REST_QUERY_PARAM_LIMIT in query_arguments:
        return error_json

    # To detect if filter arguments (valid or not) are present,
    # remove anything else valid, and check if something was left.
    # At this point sort and pagination parameters should not be
    # present as they are validated above

    # NOTE any new query key valid for non-plural
    # resources should be added here

    valid_keys_count = 0
    if REST_QUERY_PARAM_SELECTOR in query_arguments:
        valid_keys_count += 1

    if REST_QUERY_PARAM_DEPTH in query_arguments:
        valid_keys_count += 1

    invalid_keys_count = len(query_arguments) - valid_keys_count

    if invalid_keys_count > 0:
        return error_json
    else:
        return {}


def get_sorting_args(query_arguments, resource, schema, selector=None):
    sorting_args = []
    if query_arguments is not None and \
            REST_QUERY_PARAM_SORTING in query_arguments:
        sorting_args = query_arguments[REST_QUERY_PARAM_SORTING]

    sorting_values = []

    for arg in sorting_args:
        split_args = arg.split(",")
        sorting_values.extend(split_args)

    valid_sorting_values = []

    if sorting_values:

        regexp = re.compile('^([\-]?)(.*)$')

        match_order = regexp.match(sorting_values[0])

        # The parameter might include a - (indicating descending order)
        # prepended to the column name, default sorting is ascending
        # and this is represented as False in the reverse parameter
        # of sorted(), so here it's appended to the end of the
        # sorting arguments

        if match_order:
            order, value = match_order.groups()
            if order == '-':
                order = True
            else:
                order = False
            sorting_values[0] = value

            # Validate sorting keys
            valid_keys = _get_valid_keys(resource, schema, selector)

            for value in sorting_values:
                if value in valid_keys:
                    valid_sorting_values.append(value)
                else:
                    error_json = \
                        utils.to_json_error("Invalid sort column: %s" %
                                            value)
                    return {ERROR: error_json}

            if valid_sorting_values:
                valid_sorting_values.append(order)

    return valid_sorting_values


def get_query_arg(name, query_arguments):
    arg = None
    if query_arguments is not None and name in query_arguments:
        arg = query_arguments[name][0]
    return arg


def get_filters_args(query_arguments, resource, schema, selector=None):
    filters = {}
    if query_arguments is not None:
        valid_keys = _get_valid_keys(resource, schema, selector)

        for key in query_arguments:
            # NOTE any new query keys should be added to this condition
            if key in (REST_QUERY_PARAM_LIMIT, REST_QUERY_PARAM_OFFSET,
                       REST_QUERY_PARAM_DEPTH, REST_QUERY_PARAM_SORTING,
                       REST_QUERY_PARAM_SELECTOR):
                continue
            elif key in valid_keys:
                filters[key] = []
                for filter_ in query_arguments[key]:
                    filters[key].extend(filter_.split(","))
            else:
                error_json = \
                    utils.to_json_error("Invalid filter column: %s" % key)
                return {ERROR: error_json}

    return filters


def _get_valid_keys(resource, schema, selector=None):
    valid_keys = []
    if selector == OVSDB_SCHEMA_CONFIG:
        valid_keys.extend(schema.ovs_tables[resource.table].config.keys())
    elif selector == OVSDB_SCHEMA_STATUS:
        valid_keys.extend(schema.ovs_tables[resource.table].status.keys())
    elif selector == OVSDB_SCHEMA_STATS:
        valid_keys.extend(schema.ovs_tables[resource.table].stats.keys())
    else:
        valid_keys.extend(schema.ovs_tables[resource.table].config.keys())
        valid_keys.extend(schema.ovs_tables[resource.table].status.keys())
        valid_keys.extend(schema.ovs_tables[resource.table].status.keys())

    references = schema.ovs_tables[resource.table].references
    references_keys = []
    if selector is None:
        references_keys = references.keys()
    else:
        for key in references.keys():
            category = references[key].category
            if selector == category:
                references_keys.append(key)

    valid_keys.extend(references_keys)
    return valid_keys


def post_process_get_data(get_data, table, schema, sorting_args,
                          filter_args, offset, limit, selector=None):

    # GET results are groupped in status, statistics
    # and configuration but all keys (per hash) need
    # to be at the same level in order to process them
    processed_get_data = flatten_get_data(get_data)

    # TODO this should be moved to where each row is processed

    # Filter results if necessary
    if filter_args:
        processed_get_data = \
            filter_get_results(processed_get_data, filter_args, schema, table)

    # Sort results if necessary
    if sorting_args:
        # Last sorting argument is a boolean
        # indicating if sort should be reversed
        reverse_sort = sorting_args.pop()
        processed_get_data = sort_get_results(processed_get_data,
                                              sorting_args, reverse_sort)

    # Now that keys have been processed, re-groupped
    # them in status, statistics, and configuration
    processed_get_data = categorize_get_data(schema, table,
                                             processed_get_data,
                                             selector)

    # Paginate results if necessary
    processed_get_data = paginate_get_results(processed_get_data,
                                              offset, limit)

    return processed_get_data


def filter_get_results(get_data, filters, schema, table):
    filtered_data = []

    for element in get_data:
        valid = True
        for key in filters:
            if key in element:

                if key in schema.ovs_tables[table].config:
                    column_type = schema.ovs_tables[table].config[key].type
                elif key in schema.ovs_tables[table].status:
                    column_type = schema.ovs_tables[table].status[key].type
                elif key in schema.ovs_tables[table].stats:
                    column_type = schema.ovs_tables[table].stats[key].type
                elif key in schema.ovs_tables[table].references:
                    column_type = schema.ovs_tables[table].references[key].type

                filter_set = _process_filters(filters[key], column_type)

                if type(element[key]) is list:
                    value_set = set(element[key])
                else:
                    value_set = set([element[key]])

                if filter_set.difference(value_set) == filter_set:
                    valid = False

        if valid:
            filtered_data.append(element)

    return filtered_data


def _process_filters(filters, column_type):

    filter_set = set([])

    if type(filters) is list:
        filter_list = filters
    else:
        filter_list = [filters]

    for f in filter_list:
        value = convert_string_to_value_by_type(f, column_type)
        if value is not None:
            filter_set.add(value)

    return filter_set


# limit is exclusive
def paginate_get_results(get_data, offset=None, limit=None):

    data_length = len(get_data)

    if offset is None:
        if limit is None:
            return get_data
        else:
            offset = 0

    if limit is None:
        limit = data_length
    else:
        limit = offset + limit

    error_json = {}
    if offset < 0 or offset > data_length:
        error_json = utils.to_json_error("Pagination index out of range",
                                         None, REST_QUERY_PARAM_OFFSET)

    elif limit < 0:
        error_json = utils.to_json_error("Pagination index out of range",
                                         None, REST_QUERY_PARAM_LIMIT)

    elif offset >= limit:
        error_json = utils.to_json_error("Pagination offset can't be equal " +
                                         "or greater than offset + limit")

    if error_json:
        return {ERROR: error_json}

    sliced_get_data = get_data[offset:limit]

    return sliced_get_data


def sort_get_results(get_data, sort_by_columns, reverse_=False):

    # The lambda function returns a tuple with the comparable
    # values of each column, so that sorted() use them as the
    # compare keys for dictionaries in the GET results
    sorted_data = sorted(
        get_data,
        key=lambda item: tuple(sort_value_to_lower(item[k])
                               for k in sort_by_columns),
        reverse=reverse_)

    return sorted_data


def sort_value_to_lower(value):
    if isinstance(value, str):
        return value.lower()
    else:
        return value


def flatten_get_data(data):

    flattened_get_data = []

    for i in range(len(data)):
        staging_data = {}
        if OVSDB_SCHEMA_CONFIG in data[i].keys():
            staging_data.update(data[i][OVSDB_SCHEMA_CONFIG])
        if OVSDB_SCHEMA_STATS in data[i].keys():
            staging_data.update(data[i][OVSDB_SCHEMA_STATS])
        if OVSDB_SCHEMA_STATUS in data[i].keys():
            staging_data.update(data[i][OVSDB_SCHEMA_STATUS])
        flattened_get_data.append(staging_data)

    return flattened_get_data


def categorize_get_data(schema, table, data, selector=None):

    config_keys = dict(schema.ovs_tables[table].config)
    stats_keys = dict(schema.ovs_tables[table].stats)
    status_keys = dict(schema.ovs_tables[table].status)
    reference_keys = schema.ovs_tables[table].references

    for key in reference_keys:
        # depending upon the category of reference
        # pair them with the right data set
        category = reference_keys[key].category
        if category == OVSDB_SCHEMA_CONFIG:
            config_keys.update({key: reference_keys[key]})
        elif category == OVSDB_SCHEMA_STATUS:
            status_keys.update({key: reference_keys[key]})
        elif category == OVSDB_SCHEMA_STATS:
            stats_keys.update({key: reference_keys[key]})

    categorized_data = []

    for i in range(len(data)):

        stats_data = {}
        status_data = {}
        config_data = {}

        for key in config_keys:
            if key in data[i]:
                config_data[key] = data[i][key]

        for key in stats_keys:
            if key in data[i]:
                stats_data[key] = data[i][key]

        for key in status_keys:
            if key in data[i]:
                status_data[key] = data[i][key]

        staging_data = _categorize_by_selector(config_data, stats_data,
                                               status_data, selector)

        categorized_data.append(staging_data)

    return categorized_data


def _is_result_a_collection(resource):

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


def _get_depth_param(query_arguments):

    depth = 0
    depth_param = get_query_arg(REST_QUERY_PARAM_DEPTH, query_arguments)
    if depth_param:
        try:
            depth = int(depth_param)
            if depth < 0:
                error_json = utils.to_json_error("Depth parameter must be " +
                                                 "greater or equal than zero")
                return {ERROR: error_json}
        except ValueError:
            error_json = utils.to_json_error("Depth parameter must " +
                                             "be a number")
            return {ERROR: error_json}

    return depth


def _categorize_by_selector(config_data, stats_data, status_data, selector):

    data = {}
    if selector == OVSDB_SCHEMA_CONFIG:
        data = {OVSDB_SCHEMA_CONFIG: config_data}
    elif selector == OVSDB_SCHEMA_STATS:
        data = {OVSDB_SCHEMA_STATS: stats_data}
    elif selector == OVSDB_SCHEMA_STATUS:
        data = {OVSDB_SCHEMA_STATUS: status_data}
    else:
        data = {OVSDB_SCHEMA_CONFIG: config_data, OVSDB_SCHEMA_STATS:
                stats_data, OVSDB_SCHEMA_STATUS: status_data}

    return data
