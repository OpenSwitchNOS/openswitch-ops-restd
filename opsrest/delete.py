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

from opsrest.constants import *
from opsrest.utils import utils
from opsrest import verify
import httplib
from tornado.log import app_log


def delete_resource(resource, schema, txn, idl):

    if resource.next is None:
        return None

    # get the last resource pair
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    http_method = 'DELETE'

    # Check for invalid resource deletion
    if verify.verify_http_method(resource, schema, http_method) is False:
        raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

    result = verify.custom_validations(resource, schema, idl, http_method)

    if result is not True:
        app_log.debug("Custom validations failed.")
        return result

    if resource.relation == OVSDB_SCHEMA_CHILD:

        if resource.next.row is None:
            raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

        row = utils.delete_reference(resource.next, resource, schema, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        row = utils.get_row_from_resource(resource.next, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        utils.delete_all_references(resource.next, schema, idl)

    return txn.commit()
