from opsrest.constants import *
from opsrest.utils import utils
from opsrest.verify import *

from tornado.log import app_log

def delete_resource(resource, schema, txn, idl):

    if resource.next is None:
        return None

    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    if resource.relation == OVSDB_SCHEMA_CHILD:

        if resource.next.row is None:
            raise Exception({'status' : httplib.METHOD_NOT_ALLOWED})

        row = utils.delete_reference(resource.next, resource, schema, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_REFERENCE:

        # delete the reference from the table
        utils.delete_reference(resource.next, resource, None, idl)

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        row = utils.get_row(resource.next, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        utils.delete_all_references(resource.next, schema, idl)

    return txn.commit()
