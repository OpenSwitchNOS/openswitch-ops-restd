#  Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

import types

import ops.utils
import ops.constants
import urllib
from validatoradapter import ValidatorAdapter
from opsrest.constants import (REQUEST_TYPE_CREATE,
                               REQUEST_TYPE_UPDATE,
                               REQUEST_TYPE_DELETE
                                )

global_ref_list = {}

def is_row_unchanged(table_name, row, row_data, extschema, idl):
    '''
    Returns True if the row is unchanged.
    '''
    table_schema = extschema.ovs_tables[table_name]
    config_keys = table_schema.config.keys()

    for col in idl.tables[table_name].columns:
        if col not in config_keys:
            continue

        if col in row_data:
            # Check if OVSDB column value is same as the input config value
            if row.__getattr__(col) != row_data[col]:
                return False
        else:
            empty_val = ops.utils.get_empty_by_basic_type(row.__getattr__(col))
            if row.__getattr__(col) != empty_val:
                return False

    return True


# FIXME: ideally this info should come from extschema
def is_immutable_table(table, extschema):
    # TODO: Remove this list after implementing dynamic categories
    default_tables = ['Bridge', 'VRF']
    if extschema.ovs_tables[table].mutable and table not in default_tables:
        return False
    return True


def _index_to_row(index, table, extschema, idl):
    table_schema = extschema.ovs_tables[table]
    row = ops.utils.index_to_row(index, table_schema, idl)
    if row is None and table in global_ref_list:
        if index in global_ref_list[table]:
            row = global_ref_list[table][index]
    return row


def _delete(row, table, extschema, idl, txn, validator_adapter,
            parent_row = None, parent_table = None):
    for key in extschema.ovs_tables[table].children:
        if key in extschema.ovs_tables[table].references:
            child_table_name = extschema.ovs_tables[table].references[key].ref_table
            child_ref_list = row.__getattr__(key)
            if isinstance(child_ref_list, types.DictType):
                child_ref_list = child_ref_list.values()
            if child_ref_list:
                child_uuid_list = []
                for item in child_ref_list:
                    child_uuid_list.append(item.uuid)
                while child_uuid_list:
                    child = idl.tables[child_table_name].rows[child_uuid_list[0]]
                    _delete(child, child_table_name, extschema, idl, txn,
                            validator_adapter, row, table)
                    child_uuid_list.pop(0)
    # Add to validator adapter for validation and deletion
    validator_adapter.add_resource_op(REQUEST_TYPE_DELETE, row, table,
                                      parent_row, parent_table)


def setup_table(table_name, data, extschema, idl, txn, validator_adapter):

    # table is missing from config json
    if table_name not in data:
        if not is_immutable_table(table_name, extschema):
            # if mutable, empty table
            table_rows = idl.tables[table_name].rows.values()
            while table_rows:
                _delete(table_rows[0], table_name, extschema, idl, txn,
                        validator_adapter)
                table_rows = idl.tables[table_name].rows.values()
        return
    else:
        # update table
        tabledata = data[table_name]
        for rowindex, rowdata in tabledata.iteritems():

            (row_dict, _is_new, _row_unchanged_flag) = setup_row({rowindex:rowdata}, table_name,
                                         extschema, idl, txn, validator_adapter)
            if row_dict is not None and not _row_unchanged_flag:
                op = REQUEST_TYPE_CREATE if _is_new else REQUEST_TYPE_UPDATE
                validator_adapter.add_resource_op(op, row_dict.values()[0],
                                                  table_name)


def setup_references(table, data, extschema, idl):

    if table not in data:
        return

    tabledata = data[table]

    for rowindex, rowdata in tabledata.iteritems():
        setup_row_references({rowindex:rowdata}, table, extschema, idl)


def setup_row_references(rowdata, table, extschema, idl):

    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]

    row = _index_to_row(row_index, table, extschema, idl)
    if row is None:
        if not is_immutable_table(table, extschema):
            raise Exception('Row with index %s not found' % row_index)
        return

    # set references for this row
    table_schema = extschema.ovs_tables[table]
    for name, column in table_schema.references.iteritems():

        if column.category != ops.constants.OVSDB_SCHEMA_CONFIG:
            continue

        if name in table_schema.children or column.relation == ops.constants.OVSDB_SCHEMA_PARENT:
            continue

        _min = column.n_min
        _max = column.n_max
        reftable = column.ref_table

        references = None
        if (_min==1 and _max==1) and name in row_data:
            references = _index_to_row(row_data[name], reftable,
                                       extschema, idl)
            if references is None:
                raise Exception('Row with index %s not found' % row_data[name])

        elif column.kv_type:
            references = {}
            if name in row_data:
                key_type = column.kv_key_type.name
                for key,refindex in row_data[name].iteritems():
                    refrow = _index_to_row(refindex, reftable,
                                           extschema, idl)
                    if refrow is None:
                        raise Exception('Row with index %s not found' % refindex)

                    # TODO: Add support for other key types
                    if key_type == 'integer':
                        key = int(key)
                    references.update({key:refrow})
        else:
            references = []
            if name in row_data:
                for refindex in row_data[name]:
                    refrow = _index_to_row(refindex, reftable,
                                           extschema, idl)
                    if refrow is None:
                        raise Exception('Row with index %s not found' % refindex)
                    references.append(refrow)

        row.__setattr__(name, references)

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
            if child_table in extschema.ovs_tables[table].children and\
                    child_table not in extschema.ovs_tables[table].references:
                        index = str(row.uuid) + '/' + index
            setup_row_references({index:data}, child_table, extschema, idl)


def setup_row(rowdata, table_name, extschema, idl, txn,
              validator_adapter, row=None):
    """
    set up rows recursively
    """

    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = extschema.ovs_tables[table_name]

    # get row reference from table
    _new = False
    _row_unchanged_flag = False
    if row is None:
        row = ops.utils.index_to_row(row_index, table_schema, idl)

    if row is None:
        # do not add row to an immutable table
        if is_immutable_table(table_name, extschema):
            return (None, None, False)

        row = txn.insert(idl.tables[table_name])
        _new = True

        if table_name not in global_ref_list:
            global_ref_list[table_name] = {}
        global_ref_list[table_name][row_index] = row
    else:
        _row_unchanged_flag = is_row_unchanged(table_name, row, row_data,
                                               extschema, idl)

    config_keys = table_schema.config.keys()
    for key in config_keys:

        # TODO: return error if trying to set an immutable column
        # skip if trying to set an immutable column for an existing row
        if not _new and not table_schema.config[key].mutable:
            continue

        if key not in row_data:
            # skip if it's a new row
            if _new or row.__getattr__(key) is None:
                continue
            else:
                # set the right empty value
                value =  ops.utils.get_empty_by_basic_type(row.__getattr__(key))
                row.__setattr__(key, value)
        else:
            value = row_data[key]
            row.__setattr__(key, value)

    # NOTE: populate non-config index columns
    if _new:
        for key in table_schema.indexes:
            if key is 'uuid':
                continue

            if key not in table_schema.config.keys() and key in row_data:
                row.__setattr__(key, row_data[key])

    # NOTE: set up child references
    for key in table_schema.children:

        # NOTE: 'forward' type children
        if key in table_schema.references:

            child_table_name = table_schema.references[key].ref_table
            _min = table_schema.references[key].n_min
            _max = table_schema.references[key].n_max
            kv_type = table_schema.references[key].kv_type

            # no children case
            if key not in row_data or not row_data[key]:
                if not is_immutable_table(child_table_name, extschema):
                    if _new or row.__getattr__(key) is None:
                        continue
                    else:
                        value = None
                        if _min == 1 and _max == 1:
                            if kv_type:
                                value = {}
                        elif kv_type:
                            value = {}
                        else:
                            value = []
                        row.__setattr__(key, value)

            else:
                new_data = row_data[key]

                # single child
                if _min == 1 and _max == 1 and not kv_type:
                    if len(new_data) > 1:
                        raise Exception('only one reference allowed in column %s of table %s' % (key, table_name))
                    if not kv_type:
                        (_child, is_new, unchanged) = setup_row(new_data, child_table_name, extschema, idl, txn, validator_adapter)
                        if  _child is not None:
                            if not unchanged:
                                op = REQUEST_TYPE_CREATE if is_new else REQUEST_TYPE_UPDATE
                                validator_adapter.add_resource_op(op, _child.values()[0],
                                                              child_table_name,
                                                              row,
                                                              table_name)
                            if is_new:
                                _row_unchanged_flag = False
                            row.__setattr__(key, _child.values()[0])

                # kv type children references
                elif kv_type:

                    key_type = table_schema.references[key].kv_key_type.name
                    column_data = {}
                    if not _new:
                        column_data = row.__getattr__(key)

                    if _min == 1 and _max == 1:
                        if len(new_data) > 1:
                            raise Exception('only one reference allowed in column %s of table %s' % (key, table_name))

                    # delete non-existent children
                    if not _new:
                        delete_list = []
                        for index, item in column_data.iteritems():

                            # TODO: Support other types
                            if key_type == 'integer':
                                index = str(index)

                            if index not in new_data:
                                delete_list.append(item)

                        if not is_immutable_table(child_table_name, extschema):
                            while delete_list:
                                _delete(delete_list[0], child_table_name,
                                        extschema, idl, txn, validator_adapter,
                                        row, table_name)
                                delete_list.pop(0)

                    children = {}
                    for index, child_data in new_data.iteritems():
                        child = {index:child_data}

                        # TODO: Support other types
                        if key_type == 'integer':
                            index = int(index)

                        if index in column_data:
                            (_child, is_new, unchanged) = setup_row(child, child_table_name, extschema, idl, txn, validator_adapter, column_data[index])
                        else:
                            (_child, is_new, unchanged) = setup_row(child, child_table_name, extschema, idl, txn, validator_adapter)

                        if _child is not None:
                            if  not unchanged:
                                op = REQUEST_TYPE_CREATE if is_new else \
                                     REQUEST_TYPE_UPDATE
                                validator_adapter.add_resource_op(op, _child.values()[0],
                                                                  child_table_name, row,
                                                                  table_name)
                            if is_new:
                                _row_unchanged_flag = False
                            # TODO: Support other types
                            if key_type == 'integer':
                                children.update({int(_child.keys()[0]):_child.values()[0]})
                            else:
                                children.update(_child)

                    if not extschema.ovs_tables[child_table_name].index_columns:
                        for k,v in children.iteritems():

                            # TODO: Support other types
                            if key_type == 'integer':
                                k = str(k)

                            new_data[v.uuid] = new_data[k]
                            del new_data[k]

                    row.__setattr__(key, children)

                # list type children references
                else:
                    column_data = []
                    if not _new:
                        column_data = row.__getattr__(key)
                    if not _new:
                        delete_list = []
                        for item in column_data:
                            index = ops.utils.row_to_index(item, child_table_name, extschema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                        if not is_immutable_table(child_table_name, extschema):
                            while delete_list:
                                _delete(delete_list[0], child_table_name, extschema, idl, txn, validator_adapter, row, table_name)
                                delete_list.pop(0)

                    children = {}
                    for index, child_data in new_data.iteritems():
                        (_child, is_new, unchanged) = setup_row({index:child_data}, child_table_name, extschema, idl, txn, validator_adapter)
                        if _child is not None:
                            if not unchanged:
                                op = REQUEST_TYPE_CREATE if is_new else \
                                 REQUEST_TYPE_UPDATE
                                validator_adapter.add_resource_op(op, _child.values()[0],
                                                              child_table_name, row,
                                                              table_name)
                            if is_new:
                                _row_unchanged_flag = False
                            children.update(_child)

                    if not extschema.ovs_tables[child_table_name].index_columns:
                        for k,v in children.iteritems():
                            new_data[v.uuid] = new_data[k]
                            del new_data[k]

                    row.__setattr__(key, children.values())

        # Backward reference
        else:

            # get list of all 'backward' references
            column_name = None
            for x, y in extschema.ovs_tables[key].references.iteritems():
                if y.relation == ops.constants.OVSDB_SCHEMA_PARENT:
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
                            index = ops.utils.row_to_index(item,key, extschema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                    # NOTE: delete only from immutable table
                    if not is_immutable_table(key, extschema):
                        while delete_list:
                            _delete(delete_list[0], key, extschema, idl, txn,
                                    validator_adapter, row, table_name)
                            delete_list.pop(0)

                # set up children rows
                if new_data is not None:
                    for x,y in new_data.iteritems():
                        # NOTE: adding parent UUID to index
                        split_x = ops.utils.unquote_split(x)
                        split_x.insert(extschema.ovs_tables[key].index_columns.index(column_name),str(row.uuid))
                        tmp = []
                        for _x in split_x:
                            tmp.append(urllib.quote(str(_x), safe=''))
                        x = '/'.join(tmp)
                        (child, is_new, unchanged) = setup_row({x:y}, key, extschema, idl,
                                                    txn, validator_adapter)
                        if child is not None and not unchanged:
                            op = REQUEST_TYPE_CREATE if is_new else \
                            REQUEST_TYPE_UPDATE
                            validator_adapter.add_resource_op(op,
                                                              child.values()[0],
                                                              child_table_name,
                                                              row, table_name)
                            # fill the parent reference column
                            if is_new:
                                _row_unchanged_flag = False
                                child.values()[0].__setattr__(column_name, row)

    return ({row_index: row}, _new, _row_unchanged_flag)
