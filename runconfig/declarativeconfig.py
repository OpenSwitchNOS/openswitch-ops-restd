from opsrest.constants import *
from opsrest.utils import utils
import ovs
import urllib
import types


# immutable tables cannot have any additions or deletions
immutable_tables = ['Fan', 'Power_supply', 'LED', 'Temp_sensor',
                    'System', 'Subsystem', 'VRF', 'Daemon']

# READ CONFIG


def _get_row_data(row, table_name, schema, idl, index=None):

    if index is None:
        index = utils.row_to_index(row, table_name, schema, idl)

    row_data = {}

    # Routes are special case - only static routes are returned
    if table_name == 'Route' and row.__getattr__('from') != 'static':
        return

    # Iterate over all columns in the row
    table_schema = schema.ovs_tables[table_name]
    for column_name in table_schema.config.keys():
        column_data = row.__getattr__(column_name)

        # Do not include empty columns
        if column_data is None or column_data == {} or column_data == []:
            continue

        row_data[column_name] = column_data

    # Iterate over all children (forward and backward references) in the row
    for child_name in table_schema.children:

        # Forward reference
        # Two types of forward references exist
        # - regular (List of uuid)
        # - key/value type (Dict type)

        children_data = {}
        indexer = 0
        if child_name in table_schema.references:

            # Only include configurable children
            if (
                table_schema.references[child_name].category
                != OVSDB_SCHEMA_CONFIG
            ):
                continue

            column_data = row.__getattr__(child_name)
            child_table_name = table_schema.references[child_name].ref_table

            # Check kv_type references
            keys = None
            kv_type = table_schema.references[child_name].kv_type
            if kv_type and isinstance(column_data, dict):
                keys = column_data.keys()
                column_data = column_data.values()

            # Iterate through all items in column_data
            count = 0
            for item in column_data:
                if kv_type:
                    kv_index = keys[count]
                    data = _get_row_data(
                        item, child_table_name, schema,
                        idl, kv_index)
                    children_data.update({keys[count]: data.values()[0]})
                    count = count + 1
                else:
                    data = _get_row_data(item, child_table_name, schema, idl)
                    if not utils.is_default_index(child_table_name, schema):
                        indexer = indexer + 1
                        child_index = child_table_name + str(indexer)
                        data = {child_index: data.values()[0]}
                    children_data.update(data)

        # Backward reference
        else:
            column_name = None
            # Find the 'parent' name from child table (back referenced child)
            # e.g. in Route table 'vrf' column is the 'parent' column
            for (name,
                    column) in (schema.ovs_tables[child_name].
                                references.iteritems()):
                if column.relation == OVSDB_SCHEMA_PARENT:
                    # Found the parent column
                    column_name = name
                    break

            # Iterate through entire child table to find those rows belonging
            # to the same parent
            for item in idl.tables[child_name].rows.itervalues():
                # Get the parent row reference
                ref = item.__getattr__(column_name)
                # Parent reference is same as 'row' (row was passed to
                #this function) this is now the child of 'row'
                if ref.uuid == row.uuid:
                    data = _get_row_data(item, child_name, schema, idl)
                    if data is not None:
                        children_data.update(data)

        if children_data:
            row_data[child_name] = children_data

    # Iterate through 'references' from table
    for refname, refobj in table_schema.references.iteritems():

        refdata = []
        if (
            refobj.relation == OVSDB_SCHEMA_REFERENCE
            and refobj.category == OVSDB_SCHEMA_CONFIG
        ):
            reflist = row.__getattr__(refname)

            if len(reflist) == 0:
                continue

            ref_table_name = table_schema.references[refname].ref_table
            for item in reflist:
                key_index = utils.row_to_index(
                    item, ref_table_name, schema, idl)
                refdata.append(key_index)

            row_data[refname] = refdata

    return {index: row_data}


def _get_table_data(table_name, schema, idl):

    # get the table from the DB
    table = idl.tables[table_name]

    # Iterate over all rows
    table_data = {table_name: {}}

    # If table is empty return None
    if len(table.rows) == 0:
        return None

    for row in table.rows.itervalues():
        row_data = _get_row_data(row, table_name, schema, idl)
        if row_data is None or row_data == [] or row_data == {}:
            continue
        table_data[table_name].update(row_data)

    return table_data


def read(schema, idl):
    '''
    Return running configuration
    '''

    config = {}
    for table_name in schema.ovs_tables.keys():

    # Check only root table or top level table
        if schema.ovs_tables[table_name].parent is not None:
            continue

    # Get table data for root or top level table
        table_data = _get_table_data(table_name, schema, idl)

        if table_data is not None:
            config.update(table_data)

    # remove system uuid
    config['System'] = config['System'].values()[0]
    return config

# WRITE CONFIG


def setup_row(index_values, table, row_data,
              txn, reflist, schema, idl, old_row=None):

    # Initialize the flag for row to check if it is new row
    is_new = False

    # Check if row exists in DB
    if old_row is not None:
        row = old_row
    else:
        row = utils.index_to_row(index_values,
                                 schema.ovs_tables[table],
                                 idl.tables[table])

    # Create a new row if not found in DB
    if row is None:
        if table in immutable_tables:
            # Do NOT add row in Immutable table_data
            return (None, False)
        row = txn.insert(idl.tables[table])
        is_new = True

    # Routes are special case - only static routes can be updated
    if table == 'Route':
        if not is_new and row.__getattr__('from') != 'static':
            return (None, False)
        elif is_new:
            row.__setattr__('from', 'static')

    config_rows = schema.ovs_tables[table].config
    config_keys = config_rows.keys()

    # Iterate over all config keys
    for key in config_keys:
        # Ignore if row is existing and column is immutable
        if not is_new and not config_rows[key].mutable:
            continue

        # Set the column values from user config
        if key not in row_data and not is_new:
            empty_val = utils.get_empty_by_basic_type(row.__getattr__(key))
            row.__setattr__(key, empty_val)
        elif (key in row_data and
                (is_new or row.__getattr__(key) != row_data[key])):
            row.__setattr__(key, row_data[key])

    references = schema.ovs_tables[table].references
    children = schema.ovs_tables[table].children

    # Delete all the keys that don't exist
    for key in children:
        child_table = references[key].ref_table \
            if key in references else key

        # Check if table is immutable
        if child_table in immutable_tables:
            if not is_new and (key not in row_data or not row_data[key]):
                # Deep clean-up children, even if missing or empty,
                # Ignore if immutable
                if key in references:
                    kv_type = references[key].kv_type
                    if kv_type:
                        rowlist = row.__getattr__(key).values()
                    else:
                        rowlist = row.__getattr__(key)
                    clean_subtree(child_table, rowlist, txn, schema, idl)
                else:
                    clean_subtree(child_table, [], txn, schema, idl, row)
            continue

        # forward child references
        if key in references:
            table_schema = schema.ovs_tables[table]
            reference = table_schema.references[key]
            kv_type = reference.kv_type

            if not is_new and key not in row_data:
                if kv_type:
                    row.__setattr__(key, {})
                else:
                    row.__setattr__(key, [])
        else:
            # back-references
            if child_table not in row_data:
                new_data = {}
            else:
                new_data = row_data[child_table]
            remove_deleted_rows(child_table, new_data, txn, schema, idl,
                                row)

    # set up children that exist
    for key in children:
        child_table = references[key].ref_table \
            if key in references else key

        if key in row_data:

            if key in references:
                # forward referenced children
                table_schema = schema.ovs_tables[table]
                reference = table_schema.references[key]
                kv_type = reference.kv_type
                kv_key_type = None
                current_child_rows = {}

                # Key-value type children (Dict type)
                # Example - BGP_Router is KV-Type child of VRF
                if kv_type:
                    kv_key_type = reference.kv_key_type
                    if not is_new:
                        current_child_rows = row.__getattr__(key)
                    child_reference_list = {}
                # Regular children
                else:
                    child_reference_list = []

                # Iterate over each child_row
                for child_index, child_row_data in row_data[key].iteritems():
                    current_row = None
                    if kv_type:
                        if (kv_key_type is not None and
                                kv_key_type.name == 'integer'):
                            child_index = int(child_index)
                        if child_index in current_child_rows:
                            current_row = current_child_rows[child_index]
                        child_index_values = []
                    else:
                        child_index_values = utils.escaped_split(child_index)

                    (child_row, is_child_new) = setup_row(child_index_values,
                                                          child_table,
                                                          child_row_data,
                                                          txn, reflist,
                                                          schema, idl,
                                                          current_row)
                    if child_row is None:
                        continue

                    if kv_type:
                        child_reference_list.update({child_index: child_row})
                    else:
                        child_reference_list.append(child_row)
                        # Save this in global reflist
                        reflist[(child_table, child_index)] = (child_row,
                                                               is_child_new)
                if child_table not in immutable_tables:
                    row.__setattr__(key, child_reference_list)
            else:
                # backward referenced children
                parent_column = None
                references = schema.ovs_tables[child_table].references
                for col_name, col_value in references.iteritems():
                    if col_value.relation == 'parent':
                        parent_column = col_name
                        break
                # Iterate over each child_row
                for child_index, child_row_data in row_data[key].iteritems():
                    child_index_values = utils.escaped_split(child_index)

                    (child_row, is_child_new) = setup_row(child_index_values,
                                                          child_table,
                                                          child_row_data,
                                                          txn, reflist,
                                                          schema, idl)
                    if child_row is None:
                        continue
                    # Set the references column in child row
                    if parent_column is not None and is_child_new:
                        child_row.__setattr__(parent_column, row)

                    # save this in global reflist
                    reflist[(child_table, child_index)] = (child_row,
                                                           is_child_new)

    return (row, is_new)


def clean_subtree(table, entries, txn, schema, idl, parent=None):

    if parent is None:
        # Forward references
        for row in entries:
            clean_row(table, row, txn, schema, idl)
    else:
        # Backward references
        if table not in immutable_tables:
            remove_deleted_rows(table, {}, txn, schema, idl, parent)
        else:
            parent_column = None
            references_ = schema.ovs_tables[table].references
            for key, value in references_.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break
            for row in idl.tables[table].rows.itervalues():
                if parent_column is not None and \
                   row.__getattr__(parent_column) == parent:
                    clean_row(table, row, txn, schema, idl)


def clean_row(table, row, txn, schema, idl):
    references = schema.ovs_tables[table].references
    children = schema.ovs_tables[table].children
    config_rows = schema.ovs_tables[table].config

    # Clean children
    for key in children:
        if key in references:
            kv_type = references[key].kv_type
            child_table = references[key].ref_table
            if child_table not in immutable_tables:
                if kv_type:
                    row.__setattr__(key, {})
                else:
                    row.__setattr__(key, [])
            else:
                if kv_type:
                    rowlist = row.__getattr__(key).values()
                else:
                    rowlist = row.__getattr__(key)
                clean_subtree(child_table, rowlist, txn, schema, idl)
        else:
            child_table = key
            clean_subtree(child_table, [], txn, schema, idl, row)

    # Clean config fields
    for key in config_rows.keys():
        if not config_rows[key].mutable:
            continue
        empty_val = utils.get_empty_by_basic_type(row.__getattr__(key))
        row.__setattr__(key, empty_val)

    # Clean references
    for key, val in references.iteritems():
        if val.relation == 'reference' and val.mutable:
            row.__setattr__(key, [])


def setup_table(table, table_data, txn, reflist, schema, idl):

    # Iterate over each row
    for index, row_data in table_data.iteritems():
        index_values = utils.escaped_split(index)

        (row, isNew) = setup_row(index_values,
                                 table,
                                 row_data,
                                 txn, reflist, schema, idl)
        if row is None:
            continue

        # Save this in global reflist
        reflist[(table, index)] = (row, isNew)


def setup_references(table, table_data, txn, reflist, schema, idl):

    references = schema.ovs_tables[table].references

    # Iterate over every row of the table
    for index, row_data in table_data.iteritems():

        # Fetch the row from the reflist we maintain
        if (table, index) in reflist:
            (row, isNew) = reflist[(table, index)]
        else:
            # TODO: if the referenced object is not there,
            # should we throw an internal error?
            continue

        for key, value in references.iteritems():
            if value.relation == 'reference':
                if not value.mutable and not isNew:
                    continue
                new_reference_list = []
                if key in row_data:
                    ref_table = value.ref_table
                    for item in row_data[key]:
                        # TODO: missing item/references will throw
                        # an exception
                        if (ref_table, item) not in reflist:
                            continue
                        (ref_row, is_new_referenced) = reflist[(ref_table,
                                                                item)]
                        new_reference_list.append(ref_row)
                # Set the reference list
                row.__setattr__(key, new_reference_list)

        # Do the same for all child tables
        for key in schema.ovs_tables[table].children:
            if key in row_data:
                if key in references:
                    child_table = references[key].ref_table
                else:
                    child_table = key
                setup_references(child_table,
                                 row_data[key],
                                 txn, reflist,
                                 schema, idl)


def remove_deleted_rows(table, table_data, txn, schema, idl, parent=None):

    parent_column = None
    if parent is not None:
        references = schema.ovs_tables[table].references
        for key, value in references.iteritems():
            if value.relation == 'parent':
                parent_column = key
                break

    # delete rows from DB that are not in declarative config
    delete_rows = []
    for row in idl.tables[table].rows.itervalues():
        index = utils.row_to_index(row, table, schema, idl, parent)

        if (parent_column is not None and
           row.__getattr__(parent_column) != parent):
            continue

        # Routes are special case - only static routes can be deleted
        if table == 'Route' and row.__getattr__('from') != 'static':
            continue

        if index not in table_data:
            delete_rows.append(row)

    for i in delete_rows:
        i.delete()


def remove_orphaned_rows(txn, schema, idl):

    for table_name, table_schema in schema.ovs_tables.iteritems():
        if table_schema.parent is None:
            continue

        parent_column = None
        references = table_schema.references
        for key, value in references.iteritems():
            if value.relation == 'parent':
                parent_column = key
                break

        if parent_column is None:
            continue

        # Delete orphans
        delete_rows = []
        for row in idl.tables[table_name].rows.itervalues():
            parent_row = row.__getattr__(parent_column)
            if parent_row not in idl.tables[table_schema.parent].rows:
                delete_rows.append(row)
        for i in delete_rows:
            i.delete()


def write_config_to_db(schema, idl, data):

    # Create a transaction
    txn = ovs.db.idl.Transaction(idl)

    # Maintain a dict with all index:references
    reflist = {}

    # Reconstruct System record with correct UUID from the DB
    system_uuid = str(idl.tables['System'].rows.keys()[0])
    data['System'] = {system_uuid: data['System']}

    # Iterate over all top-level tables
    for table_name, table_data in schema.ovs_tables.iteritems():

        # Check if it is root table
        if table_data.parent is not None:
            continue

        if table_name not in data:
            new_data = {}
        else:
            new_data = data[table_name]

        if table_name not in immutable_tables:
            remove_deleted_rows(table_name, new_data, txn, schema, idl)

        setup_table(table_name, new_data, txn, reflist, schema, idl)

    # The tables are all set up, now connect the references together
    for table_name, value in data.iteritems():
        setup_references(table_name, data[table_name], txn, reflist,
                         schema, idl)

    # remove orphaned rows
    # TODO: FIX THIS and turn on - not critical right away since VRF
    # entry can't be removed
    # remove_orphaned_rows(txn)

    result = txn.commit_block()
    error = txn.get_error()
    return (result, error)
