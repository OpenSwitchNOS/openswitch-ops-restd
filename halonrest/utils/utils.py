import json
import ovs.db.idl
import ovs
import ovs.db.types
import types
import uuid

from halonrest.resource import Resource
from halonrest.constants import *


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
        if resource.table is None or resource.row is None or resource.column is None or idl is None:
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
        if resource.table is None or resource.row is None or resource.column is None: # or idl is None:
            return None
        else:
            return (get_row(resource, idl), resource.column)

    elif isinstance(resource, ovs.db.idl.Row):
        if column is None:
            return False
        else:
            return (resource, column)

    return None

# add a Row reference to a Resource
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
def delete_reference(reference, resource, column=None, idl=None):

    ref = check_reference(reference, idl)
    if ref is None:
        return False

    (row, column) = check_resource(resource, column, idl)
    if row is None or column is None:
        return False

    reflist = get_column(row, column, idl)
    if reflist is None:
        return False

    updated_list = []
    for item in reflist:
        if item.uuid != ref.uuid:
            updated_list.append(item)

    row.__setattr__(column, updated_list)
    return True

# create a new row, populate it with data
def setup_new_row(resource, data, schema, txn, idl):

    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None
    row = txn.insert(idl.tables[resource.table])

    # add config items
    config_keys = schema.ovs_tables[resource.table].config
    for key in config_keys:
        if key in data:
            row.__setattr__(key, data[key])

    # add reference items
    reference_keys = schema.ovs_tables[resource.table].references.keys()
    for key in reference_keys:
        if key in data:
            if isinstance(data[key], Resource):
                row.__setattr__(key, get_row(data[key], idl))
            elif type(data[key]) is types.ListType:
                reflist = []
                for item in data[key]:
                    # item is of type Resource
                    reflist.append(get_row(item, idl))
                row.__setattr__(key, reflist)
    return row

def row_to_json(row, column_keys):

    data_json = {}
    for key in column_keys:
        data_json[key] = to_json(row.__getattr__(key))

    return data_json

def to_json(data):
    type_ = type(data)

    if type_ is types.DictType:
        return dict_to_json(data)

    elif type_ is types.ListType:
        return list_to_json(data)

    elif type_ is types.UnicodeType:
        return str(data)

    elif type_ is types.BooleanType:
        return json.dumps(data)

    elif type_ is types.NoneType:
        return data

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

    if type_ is types.DictType or type_ is types.ListType or type_ is types.NoneType or type_ is types.BooleanType:
        return json_data == data

    else:
        return json_data == str(data)

def to_json_error(message, code=None, fields=None):
    dict = {"code": code, "fields": fields, "message": message}

    return dict_to_json(dict)

def dict_to_json(data):
    if not data:
        return data

    data_json = {}
    for key,value in data.iteritems():
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json[key] = str(value.uuid)
        if value is None:
            data_json[key] = 'null'
        else:
            data_json[key] = str(value)

    return data_json

def list_to_json(data):
    if not data:
        return data

    data_json = []
    for value in data:
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json.append(str(value.uuid))
        else:
            data_json.append(str(value))

    return data_json

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
            i+=1

        if i == len(indexes):
            return row

    return None

def row_to_index(table_schema, row):

    tmp = []
    for index in table_schema.indexes:
        if index == 'uuid':
            return str(row.uuid)
        else:
            tmp.append(str(row.__getattr__(index)))
    return '/'.join(tmp)
