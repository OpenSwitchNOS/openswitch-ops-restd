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
from opsrest.transaction import TransactionResult
import httplib

from tornado.log import app_log


def put_resource(data, resource, schema, txn, idl):

    # Allow PUT operation on System table
    if resource is None:
        return None

    #We want to modify System table
    if resource.next is None:
        resource_update = resource
    else:
        while True:
            if resource.next.next is None:
                break
            resource = resource.next
        resource_update = resource.next

    app_log.debug("Resource = Table: %s Relation: %s Column: %s"
                  % (resource.table, resource.relation, resource.column))
    if resource_update is not None:
        app_log.debug("Resource to Update = Table: %s "
                      % resource_update.table)

    if verify.verify_http_method(resource, schema, "PUT") is False:
        raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

    verified_data = verify.verify_data(data, resource, schema, idl, 'PUT')

    if verified_data is None:
        app_log.info("verification of data failed")
        return None

    if ERROR in verified_data:
        return verified_data

    #We want to modify System table
    if resource.next is None:
        updated_row = utils.update_row(resource, verified_data,
                                       schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_CHILD:
        '''
        Updating row from a child table
        Example:
        /system/bridges: PUT is allowed when modifying the bridge child table
        '''
        # update row, populate it with data, add it as a reference to
        #the parent resource
        updated_row = utils.update_row(resource_update,
                                       verified_data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        '''
        In this case we only modify the data of the table, but we not modify
        the back reference.
        Example:
        /system/vrfs/vrf_default/bgp_routers: PUT allowed as we are
         modifying a back referenced resource
        '''
        # row for a back referenced item contains the parent's reference
        # in the verified data
        updated_row = utils.update_row(resource_update, verified_data,
                                       schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        '''
        Updating row when we have a relationship with a top_level table
        Is not allowed to update the references in other tables.
        Example:
        /system/ports: PUT allowed as we are modifying Port to top level table
        '''
        updated_row = utils.update_row(resource_update, verified_data,
                                       schema, txn, idl)

    # TODO we need to query the modified object and return it
    result = txn.commit()
    return TransactionResult(result)
