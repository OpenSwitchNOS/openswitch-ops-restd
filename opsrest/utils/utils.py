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

import json
import ovs.db.idl
import ovs
import ovs.db.types as ovs_types
import types
import uuid
import re
import urllib

from opsrest.resource import Resource
from opsrest.constants import *
from tornado.log import app_log


# get a row from a resource
def get_row(resource, idl=None):

    if isinstance(resource, ovs.db.idl.Row):
        return resource

    elif isinstance(resource, Resource):
        if resource.table is None or resource.row is None or idl is None:
            return None

        else:
        # resource.row can be a single UUID object or a list of UUID objects
            rows = resource.row
            if type(rows) is not types.ListType:
                return idl.tables[resource.table].rows[resource.row]
            else:
                rowlist = []
                for row in rows:
                    rowlist.append(idl.tables[resource.table].rows[row])
                return rowlist

    return None


# get column items from a row or resource
def get_column(resource, column=None, idl=None):

    # if resource is a Row object
    if isinstance(resource, ovs.db.idl.Row):
        if column is None:
            return None

        if type(str(column)) is types.StringType:
            return resource.__getattr__(column)
        elif type(column) is types.ListType:
            columns = []
            for item in column:
                columns.append(resource.__getattr__(item))
            return columns
        else:
            return None

    # if resource is a Resource object
    if isinstance(resource, Resource):
        if (resource.table is None or resource.row is None or
                resource.column is None or idl is None):
            return None

        row = idl.tables[resource.table].rows[resource.row]

        if type(resource.column) is types.StringType:
            return row.__getattr__(resource.column)
        elif type(resource.column) is types.ListType:
            columns = []
            for item in resource.column:
                columns.append(row.__getattr__(item))
            return columns
        else:
            return None

    return None


# returns ovs.db.idl.Row object
def check_reference(reference, idl=None):

    if isinstance(reference, Resource):
        if reference.table is None or reference.row is None or idl is None:
            return None
        else:
            ref = get_row(reference, idl)
            return ref

    elif isinstance(reference, ovs.db.idl.Row):
        return reference

    return None


# returns a tuple of consisting of (ovs.db.idl.Row, column)
def check_resource(resource, column=None, idl=None):

    if isinstance(resource, Resource):
        if (resource.table is None or resource.row is None or
                resource.column is None):  # or idl is None:
            return None
        else:
            return (get_row(resource, idl), resource.column)

    elif isinstance(resource, ovs.db.idl.Row):
        if column is None:
            return False
        else:
            return (resource, column)

    return None


# add a Row reference that is of type {key:reference}
def add_kv_reference(key, reference, resource, idl):

    row = idl.tables[resource.table].rows[resource.row]
    kv_references = get_column(row, resource.column)

    updated_kv_references = {}
    for k,v in kv_references.iteritems():
        updated_kv_references[k] = v

    updated_kv_references[key] = reference
    row.__setattr__(resource.column, updated_kv_references)
    return True

# add a Row reference


def add_reference(reference, resource, column=None, idl=None):

    ref = check_reference(reference, idl)
    if ref is None:
        return False

    (row, column) = check_resource(resource, column, idl)
    if row is None or column is None:
        return False

    reflist = get_column(row, column)

    # a list of Row elements
    if len(reflist) == 0 or isinstance(reflist[0], ovs.db.idl.Row):
        updated_list = []
        for item in reflist:
            updated_list.append(item)
        updated_list.append(ref)
        row.__setattr__(column, updated_list)
        return True

    # a list-of-list of Row elements
    elif type(reflist[0]) is types.ListType:
        for _reflist in reflist:
            updated_list = []
            for item in _reflist:
                updated_list.append(item)
            updated_list.append(ref)
            row.__setattr__(column, updated_list)
        return True

    return False


# delete a Row reference from a Resource
def delete_reference(resource, parent, schema, idl):

    # kv type reference
    ref = None
    if schema.ovs_tables[parent.table].references[parent.column].kv_type:
        app_log.debug('Deleting KV type reference')
        key = resource.index[0]
        parent_row = idl.tables[parent.table].rows[parent.row]
        kv_references = get_column(parent_row, parent.column)
        updated_kv_references = {}
        for k,v in kv_references.iteritems():
            if str(k) == key:
                ref = v
            else:
                updated_kv_references[k] = v

        parent_row.__setattr__(parent.column, updated_kv_references)
    else:
        # normal reference
        app_log.debug('Deleting normal reference')
        ref = get_row(resource, idl)
        parent_row = get_row(parent, idl)
        reflist = get_column(parent_row, parent.column, idl)

        if reflist is None:
            app_log.debug('reference list is empty')
            return False

        updated_references = []
        for item in reflist:
            if item.uuid != ref.uuid:
                updated_references.append(item)

        parent_row.__setattr__(parent.column, updated_references)

    return ref


def delete_all_references(resource, schema, idl):
    row = get_row(resource, idl)
    #We get the tables that reference the row to delete table
    tables_reference = schema.references_table_map[resource.table]
    #Get the table name and column list we is referenced
    for table_name, columns_list in tables_reference.iteritems():
        app_log.debug("Table %s" % table_name)
        app_log.debug("Column list %s" % columns_list)
        #Iterate each row to see wich tuple has the reference
        for uuid, row_ref in idl.tables[table_name].rows.iteritems():
            #Iterate over each reference column and check if has the reference
            for column_name in columns_list:
                #get the referenced values
                reflist = get_column(row_ref, column_name, idl)
                if reflist is not None:
                    #delete the reference on that row and column
                    delete_row_reference(reflist, row, row_ref, column_name)


def delete_row_reference(reflist, row, row_ref, column):
    updated_list = []
    for item in reflist:
        if item.uuid != row.uuid:
            updated_list.append(item)
    row_ref.__setattr__(column, updated_list)


# create a new row, populate it with data
def setup_new_row(resource, data, schema, txn, idl):

    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None
    row = txn.insert(idl.tables[resource.table])

    # add config items
    set_config_fields(resource, row, data, schema)

    # add reference items
    set_reference_items(resource, row, data, schema, idl)

    return row


#Update columns from a row
def update_row(resource, data, schema, txn, idl):
    #Verify if is a Resource instance
    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None

    #get the row that will be modified
    row = get_row(resource, idl)

    #Update config items
    set_config_fields(resource, row, data, schema)

    # add or modify reference items (Overwrite references)
    set_reference_items(resource, row, data, schema, idl)

    return row


# set each config data on each column
def set_config_fields(resource, row, data, schema):
    config_keys = schema.ovs_tables[resource.table].config
    for key in config_keys:
        if key in data:
            row.__setattr__(key, data[key])


# set the reference items in the row
def set_reference_items(resource, row, data, schema, idl):
    # set new reference items
    reference_keys = schema.ovs_tables[resource.table].references.keys()
    for key in reference_keys:
        if key in data:
            app_log.debug("Adding Reference, the key is %s" % key)
            if isinstance(data[key], Resource):
                row.__setattr__(key, get_row(data[key], idl))
            elif type(data[key]) is types.ListType:
                reflist = []
                for item in data[key]:
                    row_ref = get_row(item, idl)
                    # item is of type Resource
                    reflist.append(row_ref)
                #Set data on the column
                row.__setattr__(key, reflist)


def row_to_json(row, column_keys):

    data_json = {}
    for key in column_keys:

        attribute = row.__getattr__(key)
        attribute_type = type(attribute)

        # Convert single element lists to scalar
        # if schema defines a max of 1 element
        if attribute_type is list and column_keys[key].n_max == 1:
            if len(attribute) > 0:
                attribute = attribute[0]
            else:
                attribute = get_empty_by_basic_type(column_keys[key].type)

        value_type = column_keys[key].type
        if attribute_type is dict:
            value_type = column_keys[key].value_type

        data_json[key] = to_json(attribute, value_type)

    return data_json


def get_empty_by_basic_type(data):
    type_ = type(data)

    # If data is already a type, just use it
    if type_ is type:
        type_ = data

    if type_ is types.DictType:
        return {}

    elif type_ is types.ListType:
        return []

    elif type_ in ovs_types.StringType.python_types:
        return ''

    elif type_ in ovs_types.IntegerType.python_types:
        return 0

    elif type_ in ovs_types.RealType.python_types:
        return 0.0

    elif type_ is types.BooleanType:
        return False

    elif type_ is types.NoneType:
        return None

    else:
        return ''


def to_json(data, value_type=None):
    type_ = type(data)

    if type_ is types.DictType:
        return dict_to_json(data, value_type)

    elif type_ is types.ListType:
        return list_to_json(data, value_type)

    elif type_ in ovs_types.StringType.python_types:
        return str(data)

    elif (type_ in ovs_types.IntegerType.python_types or
            type_ in ovs_types.RealType.python_types):
        return data

    elif type_ is types.BooleanType:
        return json.dumps(data)

    elif type_ is types.NoneType:
        return get_empty_by_basic_type(value_type)

    elif type_ is uuid.UUID:
        return str(data)

    elif type_ is ovs.db.idl.Row:
        return str(data.uuid)

    else:
        return str(data)


def has_column_changed(json_data, data):
    json_type_ = type(json_data)
    type_ = type(data)

    if json_type_ != type_:
        return False

    if (type_ is types.DictType or
            type_ is types.ListType or
            type_ is types.NoneType or
            type_ is types.BooleanType or
            type_ in ovs_types.IntegerType.python_types or
            type_ in ovs_types.RealType.python_types):
        return json_data == data

    else:
        return json_data == str(data)


def to_json_error(message, code=None, fields=None):
    dictionary = {"code": code, "fields": fields, "message": message}

    return dict_to_json(dictionary)


def dict_to_json(data, value_type=None):
    if not data:
        return data

    data_json = {}
    for key, value in data.iteritems():
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json[key] = str(value.uuid)

        elif value is None:
            data_json[key] = get_empty_by_basic_type(value_type)

        elif (type_ in ovs_types.IntegerType.python_types or
                type_ in ovs_types.RealType.python_types):
            data_json[key] = value

        else:
            data_json[key] = str(value)

    return data_json


def list_to_json(data, value_type=None):
    if not data:
        return data

    data_json = []
    for value in data:
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json.append(str(value.uuid))

        elif (type_ in ovs_types.IntegerType.python_types or
                type_ in ovs_types.RealType.python_types):
            data_json.append(value)

        elif value is None:
            data_json.append(get_empty_by_basic_type(value_type))

        else:
            data_json.append(str(value))

    return data_json

'''
This subroutine fetches the row reference using index_values.
index_values is a list which contains the combination indices
that are used to identify a resource.
'''

def index_to_row(index_values, table_schema, dbtable):

    indexes = table_schema.indexes
    if len(index_values) != len(indexes):
        return None

    for row in dbtable.rows.itervalues():
        i = 0
        for index, value in zip(indexes, index_values):
            if index == 'uuid':
                if str(row.uuid) != value:
                    break
            elif str(row.__getattr__(index)) != value:
                break

            # matched index
            i += 1

        if i == len(indexes):
            return row

    return None

'''
This subroutine fetches the row reference using the index as key.
Current feature uses a single index and not a combination of multiple
indices. This is used for the new key/uuid type forward references introduced
for BGP
'''
def kv_index_to_row(index_values, parent, idl):

    index = index_values[0]
    column = parent.column
    row = idl.tables[parent.table].rows[parent.row]

    column_item = row.__getattr__(parent.column)
    for key, value in column_item.iteritems():
        if str(key) == index:
            return value

    return None

def row_to_index(table_schema, row, uuid_sequencer = None):

    tmp = []
    for index in table_schema.indexes:
        if index == 'uuid':
            if uuid_sequencer is None:
                return str(row.uuid)

            # Generate dummy index for all entries in tables that
            #don't have anything besides UUID
            if (table_schema.name, str(row.uuid)) not in uuid_sequencer:

                if (table_schema.name, 'last_sequence') not in uuid_sequencer:
                    uuid_sequencer[(table_schema.name, 'last_sequence')] = 0

                next_sequence = uuid_sequencer[(table_schema.name,
                                                'last_sequence')] + 1
                uuid_sequencer[(table_schema.name, 'last_sequence')] = \
                    next_sequence
                uuid_sequencer[(table_schema.name, str(row.uuid))] = \
                    table_schema.name + str(next_sequence)

            return uuid_sequencer[(table_schema.name, str(row.uuid))]
        else:
            val = str(row.__getattr__(index))
            tmp.append(str(val.replace('/', '\/')))

    return '/'.join(tmp)


def escaped_split(s_in):
    strings = re.split(r'(?<!\\)/', s_in)
    res_strings = []

    for s in strings:
        s = s.replace('\\/', '/')
        res_strings.append(s)

    return res_strings


def get_reference_parent_uri(table_name, row, schema, idl):
    uri = ''
    path = get_parent_trace(table_name, row, schema, idl)
    #Don't include Open_vSwitch table
    for table_name, indexes in path[1:]:
        plural_name = schema.ovs_tables[table_name].plural_name
        uri += str(plural_name) + '/' + "/".join(indexes) + '/'
    app_log.debug("Reference uri %s" % uri)
    return uri

'''
Get the parent trace to one row
Returns (table, index) list
'''


def get_parent_trace(table_name, row, schema, idl):
    table = schema.ovs_tables[table_name]
    path = []
    while table.parent is not None and row is not None:
        parent_table = schema.ovs_tables[table.parent]
        column = get_parent_column_ref(parent_table.name, table.name, schema)
        row = get_parent_row(parent_table.name, row, column, schema, idl)
        index_list = get_table_key(row, parent_table.name, schema)
        table_path = (parent_table.name, index_list)
        path.insert(0, table_path)
        table = parent_table
    return path

'''
Get column name where the child table is being referenced
Returns column name
'''


def get_parent_column_ref(table_name, table_ref, schema):
    table = schema.ovs_tables[table_name]
    for column_name, reference in table.references.iteritems():
        if reference.ref_table == table_ref and reference.relation == 'child':
            return column_name

'''
Get the row where the item is being referenced
Returns idl.Row object
'''


def get_parent_row(table_name, row, column, schema, idl):
    table = schema.ovs_tables[table_name]
    for uuid, row_ref in idl.tables[table_name].rows.iteritems():
        reflist = get_column(row_ref, column, idl)
        for item in reflist:
            if item.uuid == row.uuid:
                return row_ref

'''
Get the row index
Return the row index
'''


def get_table_key(row, table_name, schema):
    table = schema.ovs_tables[table_name]
    indexes = table.indexes
    index_list = []
    for index in indexes:
        if index == 'uuid':
            index_list.append(str(row.uuid))
        else:
            value = urllib.quote(str(row.__getattr__(index)), safe='')
            index_list.append(value)
    return index_list
