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

import ovs.db.idl

import ops.utils
import ops.constants
import urllib


global_ref_list = {}


def _index_to_row(index, table, extschema, idl):
    table_schema = extschema.ovs_tables[table]
    row = ops.utils.index_to_row(index, table_schema, idl)
    if row is None and table in global_ref_list:
        if index in global_ref_list[table]:
            row = global_ref_list[table][index]
    return row


def _delete_row_list(delete_list, table, extschema, idl):
    not_deleted = []
    for uuid in delete_list:
        row = idl.tables[table].rows[uuid]
        if not _delete_row(row, table, extschema, idl):
            not_deleted.append(uuid)
    return not_deleted


def _delete_row(row, table, extschema, idl):

    # delete only those children that are configurable
    delete = True
    for key in extschema.ovs_tables[table].children:
        if key in extschema.ovs_tables[table].references:

            child_table = extschema.ovs_tables[table].references[key].ref_table
            child_references = row.__getattr__(key)

            if not child_references:
                continue
            elif isinstance(child_references, ovs.db.idl.Row):
                child_references = [child_references]
            elif isinstance(child_references, types.DictType):
                child_references = child_references.values()

            delete_list = []
            for child_row in child_references:
                if ops.utils.delete_row_check(child_row, child_table, extschema, idl):
                    delete_list.append(child_row.uuid)

            # do not delete row if at least one child remains
            if delete:
                if len(child_references) > len(delete_list):
                    delete = False

            # delete rows
            if delete_list:
                _delete_row_list(delete_list, child_table, extschema, idl)

    # delete row only if all its children are deleted
    if delete:
        row.delete()

    return delete


def setup_table(table, data, extschema, idl, txn):
    table_schema = extschema.ovs_tables[table]
    # table is missing from applied config
    if table not in data:

        delete_list = []
        for uuid, row in idl.tables[table].rows.iteritems():
            if ops.utils.delete_row_check(row, table, extschema, idl):
                delete_list.append(uuid)

        # delete rows
        if delete_list:
            _delete_row_list(delete_list, table, extschema, idl)
    else:
        # update table
        tabledata = data[table]
        for rowindex, rowdata in tabledata.iteritems():
            setup_row({rowindex:rowdata}, table, extschema, idl, txn)


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
        return

    # set references for this row
    table_schema = extschema.ovs_tables[table]
    categories = ops.utils.get_dynamic_categories(row, table, extschema, idl)
    for name, column in table_schema.references.iteritems():
        category = categories[ops.constants.OVSDB_SCHEMA_REFERENCE][name].category
        if category != ops.constants.OVSDB_SCHEMA_CONFIG:
            continue

        if name in table_schema.children or column.relation == ops.constants.OVSDB_SCHEMA_PARENT:
            continue

        _min = column.n_min
        _max = column.n_max
        reftable = column.ref_table
        kv_type = column.kv_type

        references = None
        if  _max==1 and not kv_type and name in row_data:
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


def setup_row(rowdata, table_name, extschema, idl, txn, row=None):
    """
    set up rows recursively
    """
    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = extschema.ovs_tables[table_name]

    # get row reference from table
    new = False
    if row is None:
        row = ops.utils.index_to_row(row_index, table_schema, idl)

    if row is None:
        row = ops.utils.insert_row_check(row_data, table_name, extschema, idl, txn)
        if not row:
            return (None, None)
        else:
            new = True

        if table_name not in global_ref_list:
            global_ref_list[table_name] = {}
        global_ref_list[table_name][row_index] = row

    else:
        ops.utils.set_config_columns(row_data, row, table_name, extschema)

    # configure children
    for key in table_schema.children:
        if key in table_schema.references:

            child_table_name = table_schema.references[key].ref_table
            _min = table_schema.references[key].n_min
            _max = table_schema.references[key].n_max
            kv_type = table_schema.references[key].kv_type

            # no children data present in the given configuration
            if key not in row_data or not row_data[key]:
                if not new:
                    updated_data = _empty_child_column(key, table_name, row, extschema, idl, None)
                    row.__setattr__(key, updated_data)
            else:
                new_data = row_data[key]

                # single child instance
                if _max == 1 and not kv_type:
                    if len(new_data) > 1:
                        raise Exception('maximum one reference is allowed in column %s of table %s' % (key, table_name))

                    (_child, is_new) = setup_row(new_data, child_table_name, extschema, idl, txn)
                    if _child:
                        row.__setattr__(key, _child.values()[0])

                # kv type children references
                elif kv_type:

                    column_data = {}
                    updated_data = {}
                    if _min == 1 and _max == 1:
                        if len(new_data) > 1:
                            raise Exception('only one reference allowed in column %s of table %s' % (key, table_name))

                    if not new:
                        column_data = row.__getattr__(key)
                        updated_data = _empty_child_column(key, table_name, row, extschema, idl, new_data)

                    # setup new rows
                    key_type = table_schema.references[key].kv_key_type.name
                    children = {}

                    for index, child_data in new_data.iteritems():

                        # TODO: Support other types
                        if key_type == 'integer':
                            index = int(index)

                        child = {index:child_data}
                        if index in column_data:
                            (_child, is_new) = setup_row(child, child_table_name, extschema, idl, txn, column_data[index])
                        else:
                            (_child, is_new) = setup_row(child, child_table_name, extschema, idl, txn)

                        if _child is not None:
                            if key_type == 'integer':
                                children.update({int(_child.keys()[0]):_child.values()[0]})
                            else:
                                children.update(_child)

                    # replace child index with UUID in json data to optimise setup_row_reference call later
                    if not extschema.ovs_tables[child_table_name].index_columns:
                        for k,v in children.iteritems():
                            # TODO: Support other types
                            if key_type == 'integer':
                                k = str(k)

                            new_data[v.uuid] = new_data[k]
                            del new_data[k]

                    if not updated_data:
                        updated_data = children
                    else:
                        updated_data.update(children)
                    row.__setattr__(key, updated_data)

                # list type children references
                else:
                    updated_data = []
                    if not new:
                        updated_data = _empty_child_column(key, table_name, row, extschema, idl, new_data)

                    # setup new rows
                    children = {}
                    for index, child_data in new_data.iteritems():
                        (_child, is_new) = setup_row({index:child_data}, child_table_name, extschema, idl, txn)
                        if _child is not None:
                            children.update(_child)

                    # replace child index with UUID in json data to optimise setup_row_reference call later
                    if not extschema.ovs_tables[child_table_name].index_columns:
                        for k,v in children.iteritems():
                            new_data[v.uuid] = new_data[k]
                            del new_data[k]

                    # add new rows to updated data
                    if not updated_data:
                        updated_data = children.values()
                    else:
                        updated_data += children.values()
                    row.__setattr__(key, updated_data)

        # Backward reference
        else:

            # get list of all backward references
            column_name = None
            for x, y in extschema.ovs_tables[key].references.iteritems():
                if y.relation == ops.constants.OVSDB_SCHEMA_PARENT:
                    column_name = x
                    break

            # delete non-existent rows

            # get list of all rows with same parent
            if not new:
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
                        for item in delete_list:
                            if ops.utils.delete_row_check(item, key, extschema, idl):
                                delete_list.append(item.uuid)
                    else:
                        for item in current_list:
                            index = ops.utils.row_to_index(item,key, extschema, idl)
                            if index not in new_data:
                                if ops.utils.delete_row_check(item, key, extschema, idl):
                                    delete_list.append(item.uuid)

                    if delete_list:
                        _delete_row_list(delete_list, key, extschema, idl)

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
                        (child, is_new) = setup_row({x:y}, key, extschema, idl, txn)

                        # fill the parent reference column
                        if child is not None and is_new:
                            child.values()[0].__setattr__(column_name, row)

    return ({row_index:row}, new)

def _empty_child_column(column, table, row, extschema, idl, new_data=None):
    column_data = row.__getattr__(column)
    child_table = extschema.ovs_tables[table].references[column].ref_table

    if not column_data:
        return None
    if isinstance(column_data, ovs.db.idl.Row):
        index = None
        if new_data:
            index = ops.utils.row_to_index(column_data, child_table, extschema, idl)
        if not new_data or index not in new_data:
            if ops.utils.delete_row_check(column_data, table, extschema, idl):
                if _delete_row(column_data, child_table, extschema, idl):
                    return None
        return column_data
    elif isinstance(column_data, list):
        delete_list = []
        remainder_list = []
        for child in column_data:
            index = None
            if new_data:
                index = ops.utils.row_to_index(child, child_table, extschema, idl)
            if not new_data or index not in new_data:
                if ops.utils.delete_row_check(child, child_table, extschema, idl):
                    delete_list.append(child.uuid)
                    continue
            remainder_list.append(child)

        if delete_list:
            failed_delete = _delete_row_list(delete_list, child_table, extschema, idl)
            if failed_delete:
                for item in failed_delete:
                    remainder_list.append(idl.tables[child_table].rows[item])
        return remainder_list
    elif isinstance(column_data, dict):
        delete_list = {}
        remainder_list = {}
        key_type = extschema.ovs_tables[table].references[column].kv_key_type.name
        for index, child in column_data.iteritems():
            # TODO: handle other types
            c_index = index
            if key_type == 'integer':
                c_index = str(index)

            if not new_data or c_index not in new_data:
                if ops.utils.delete_row_check(child, child_table, extschema, idl):
                    delete_list.update({child.uuid:index})
                    continue
            remainder_list.update({index:child})

        if delete_list:
            failed_delete = _delete_row_list(delete_list.keys(), child_table, extschema, idl)
            for item in failed_delete:
                child_row = idl.tables[child_table].rows[item]
                remainder_list.update({delete_list[item]:child_row})
        return remainder_list
