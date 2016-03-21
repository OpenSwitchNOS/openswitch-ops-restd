#  Copyright (C) 2015 Hewlett Packard Enterprise Development LP
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import ovs
import urllib
import types
import json
import uuid

from constants import *
import ovs.db.types as ovs_types

def escaped_split(s_in):
    s_in = s_in.split('/')
    s_in = [urllib.unquote(i) for i in s_in if i != '']
    return s_in


def get_empty_by_basic_type(data):
    type_ = type(data)

    # If data is already a type, just use it
    if type_ is type:
        type_ = data
    elif type_ is ovs_types.AtomicType:
        type_ = data

    if type_ is types.DictType:
        return {}

    elif type_ is types.ListType:
        return []

    elif type_ in ovs_types.StringType.python_types or \
            type_ is ovs_types.StringType:
        return ''

    elif type_ in ovs_types.IntegerType.python_types or \
            type_ is ovs_types.IntegerType:
        return 0

    elif type_ in ovs_types.RealType.python_types or \
            type_ is ovs_types.RealType:
        return 0.0

    elif type_ is types.BooleanType or \
            type_ is ovs_types.BooleanType:
        return False

    elif type_ is types.NoneType:
        return None

    else:
        return ''


def row_to_index(row, table, restschema, idl, parent_row=None):

    index = None
    schema = restschema.ovs_tables[table]
    indexes = schema.indexes

    # if index is just UUID
    if len(indexes) == 1 and indexes[0] == 'uuid':

        if schema.parent is not None:
            parent = schema.parent
            parent_schema = restschema.ovs_tables[parent]

            # check in parent if a child 'column' exists
            column_name = schema.plural_name
            if column_name in parent_schema.references:
                # look in all resources
                parent_rows = None
                if parent_row is not None:
                    # TODO: check if this row exists in parent table
                    parent_rows = [parent_row]
                else:
                    parent_rows = idl.tables[parent].rows

                for item in parent_rows.itervalues():
                    column_data = item.__getattr__(column_name)

                    if isinstance(column_data, types.ListType):
                        for ref in column_data:
                            if ref.uuid == row:
                                index = str(row.uuid)
                                break
                    elif isinstance(column_data, types.DictType):
                        for key, value in column_data.iteritems():
                            if value == row:
                                # found the index
                                index = key
                                break

                    if index is not None:
                        break
        else:
            index = str(row.uuid)
    else:
        tmp = []
        for item in indexes:
            tmp.append(urllib.quote(str(row.__getattr__(item)), safe=''))
        index = '/'.join(tmp)

    return index


def index_to_row(index, table_schema, dbtable):
    """
    This subroutine fetches the row reference using index.
    index is either of type uuid.UUID or is a uri escaped string which contains
    the combination indices that are used to identify a resource.
    """
    table = table_schema.name
    if isinstance(index, uuid.UUID):
        # index is of type UUID
        if index in dbtable.rows:
            return dbtable.rows[index]
        else:
            raise Exception("""resource with UUID %(i) not found
                            in table %(j)
                            """ % {"i":str(index), "j":table})
    else:
        # index is an escaped combine indices string
        index_values = escaped_split(index)
        indexes = table_schema.indexes

        # if table has no indexes, we create a new entry
        if not table_schema.index_columns:
            return None

        if len(index_values) != len(indexes):
            raise Exception('Combination index error for table %s' % table)

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


def _delete(row, table, schema, idl, txn):
    for key in schema.ovs_tables[table].children:
        if key in schema.ovs_tables[table].references:
            child_table_name = schema.ovs_tables[table].references[key].ref_table
            child_ref_list = row.__getattr__(key)
            if isinstance(child_ref_list, types.DictType):
                child_ref_list = child_ref_list.values()
            if child_ref_list:
                child_uuid_list = []
                for item in child_ref_list:
                    child_uuid_list.append(item.uuid)
                while child_uuid_list:
                    child = idl.tables[child_table_name].rows[child_uuid_list[0]]
                    _delete(child, child_table_name, schema, idl, txn)
                    child_uuid_list.pop(0)
    row.delete()


def setup_table(table_name, data, schema, idl, txn):
    if table_name not in data:
        table_rows = idl.tables[table_name].rows.values()
        while table_rows:
            _delete(table_rows[0], table_name, schema, idl, txn)
            table_rows = idl.tables[table_name].rows.values()

        return

    # update table
    tabledata = data[table_name]

    for rowindex, rowdata in tabledata.iteritems():
        # TODO: This has an unfortunate effect of searching through
        # the table from the beginning in index_to_row call. If we
        # had indexes mapped to Rows then this issue will go away
        setup_row({rowindex:rowdata}, table_name, schema, idl, txn)


def setup_references(table, data, schema, idl):
    if table not in data:
        return

    tabledata = data[table]

    for rowindex, rowdata in tabledata.iteritems():
        setup_row_references({rowindex:rowdata}, table, schema, idl)


def setup_row_references(rowdata, table, schema, idl):
    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = schema.ovs_tables[table]
    idl_table = idl.tables[table]

    row = index_to_row(row_index, table_schema, idl_table)

    # set references for this row
    for name, column in table_schema.references.iteritems():

        if name in table_schema.children or column.relation == OVSDB_SCHEMA_PARENT:
            continue

        if name not in row_data:
            row.__setattr__(name, [])
        else:
            reflist = []
            reftable = column.ref_table
            refidl = idl.tables[reftable]
            refschema = schema.ovs_tables[reftable]

            for refindex in row_data[name]:
                refrow = index_to_row(refindex, refschema, refidl)
                reflist.append(refrow)
            row.__setattr__(name, reflist)

    for child in table_schema.children:

        # check if child data exists
        if child not in row_data:
            continue

        # get the child table name
        child_data = row_data[child]
        child_table = None
        if child in table_schema.references:
            child_table = table_schema.references[child].ref_table
        else:
            child_table = child

        for index, data in child_data.iteritems():
            setup_row_references({index:data}, child_table, schema, idl)


def setup_row(rowdata, table_name, schema, idl, txn):
    """
    set up rows recursively
    """
    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = schema.ovs_tables[table_name]
    idl_table = idl.tables[table_name]

    # get row reference from table
    _new = False
    row = index_to_row(row_index, table_schema, idl_table)
    if row is None:
        row = txn.insert(idl.tables[table_name])
        _new = True

    # NOTE: populate configuration data
    config_keys = table_schema.config.keys()
    for key in config_keys:

        # TODO: return error if trying to set an immutable column
        # skip if trying to set an immutable column for an existing row
        if not _new and table_schema.config[key].mutable is False:
            continue

        if key not in row_data:
            # skip if it's a new row
            if _new or row.__getattr__(key) is None:
                continue
            else:
                # set the right empty value
                value =  get_empty_by_basic_type(row.__getattr__(key))
        else:
            value = row_data[key]

        row.__setattr__(key, value)

    # NOTE: populate non-config index columns
    if _new:
        for key in table_schema.indexes:
            if key is 'uuid':
                continue

            if key not in table_schema.config.keys():
                row.__setattr__(key, row_data[key])

    # NOTE: set up child references
    for key in table_schema.children:

        # NOTE: 'forward' type children
        if key in table_schema.references:

            child_table_name = table_schema.references[key].ref_table

            # skip immutable column
            if not _new and not table_schema.references[key].mutable:
                continue

            # set up empty reference list
            if key not in row_data:
                if _new or row.__getattr__(key) is None:
                    continue
                else:
                   value = get_empty_by_basic_type(row.__getattr__(key))
                row.__setattr__(key, value)

            else:
                new_data = row_data[key]

                # {key:UUID} type of reference check
                kv_type = table_schema.references[key].kv_type

                # if not a new row, delete non-existent child references
                if not _new:
                    current_list = row.__getattr__(key)
                    if current_list:
                        if kv_type:
                            current_list = current_list.values()
                        delete_list = []
                        for item in current_list:
                            index = row_to_index(item, child_table_name, schema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                        while delete_list:
                            _delete(delete_list[0], child_table_name, schema, idl, txn)
                            delete_list.pop(0)

                # setup children
                children = {}
                for index, child_data in new_data.iteritems():
                    (_child, is_new) = setup_row({index:child_data}, child_table_name, schema, idl, txn)
                    children.update(_child)

                # NOTE: If the child table doesn't have indexes, replace json index
                # with row.uuid
                if not schema.ovs_tables[child_table_name].index_columns:
                    for k,v in children.iteritems():
                        new_data[v.uuid] = new_data[k]
                        del new_data[k]

                if kv_type:
                    if table_schema.references[key].kv_key_type.name == 'integer':
                        tmp = {}
                        for k,v in children.iteritems():
                            tmp[int(k)] = v
                        children = tmp
                    row.__setattr__(key, children)
                else:
                    row.__setattr__(key, children.values())

        # Backward reference
        else:

            # get list of all 'backward' references
            column_name = None
            for x, y in schema.ovs_tables[key].references.iteritems():
                if y.relation == OVSDB_SCHEMA_PARENT:
                    column_name = x
                    break

            # delete non-existent rows

            # get list of all rows with same parent
            if not _new:
                current_list = []
                for item in idl.tables[key].rows.itervalues():
                    parent = item.__getattr__(column_name)
                    if parent.uuid == row.uuid:
                        current_list.append(item)

                new_data = None
                if key in row_data:
                    new_data = row_data[key]

                if current_list:
                    delete_list = []
                    if new_data is None:
                        delete_list = current_list
                    else:
                        for item in current_list:
                            index = row_to_index(item,key, schema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                    while delete_list:
                        _delete(delete_list[0], key, schema, idl, txn)
                        delete_list.pop(0)

                # set up children rows
                if new_data is not None:
                    for x,y in new_data.iteritems():
                        (child, is_new) = setup_row({x:y}, key, schema, idl, txn)

                        # fill the parent reference column
                        if is_new:
                            child.values()[0].__setattr__(column_name, row)

    return ({row_index:row}, _new)
