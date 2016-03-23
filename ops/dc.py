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

import _read, _write
import ops.constants

from ovs.db.idl import SchemaHelper, Idl

def register(extschema, ovsschema, ovsremote):
    """Register interest in all configuration and index
    columns for all tables in ovsschema.

    Args:
        extschema (opslib.RestSchema): This is the
            parsed extended-schema (vswitch.extschema) object.
        ovsschema: OVSDB schema file
        ovsremote: OVSDB remote socket

    Returns:
        ovs.db.idl.Idl instance
    """

    schema_helper = SchemaHelper(ovsschema)

    for tablename, tableschema in extschema.ovs_tables.iteritems():

        register_columns = []

        # configuration columns
        config_columns = [str(key) for key in tableschema.config.keys()]
        # reference columns
        reference_columns = [str(key) for key in tableschema.references.keys()]


        # index columns
        for item in tableschema.index_columns:
            if not item in config_columns:
                register_columns.append(str(item))

        register_columns += config_columns
        register_columns += reference_columns

        schema_helper.register_columns(str(tablename), register_columns)

    idl = Idl(ovsremote, schema_helper)
    return idl


def read(extschema, idl):
    """Read the OpenSwitch OVSDB database

    Args:
        extschema (opslib.RestSchema): This is the
            parsed extended-schema (vswitch.extschema) object.
        idl (ovs.db.idl.Idl): This is the IDL object that
            represents the OVSDB IDL.

    Returns:
        dict: Returns a Python dictionary object containing
            data read from all OVSDB tables and arranged according
            to the relationship between various tables as
            described in vswitch.extschema
    """

    config = {}
    for table_name in extschema.ovs_tables.keys():

    # Check only root table or top level table
        if extschema.ovs_tables[table_name].parent is not None:
            continue

    # Get table data for root or top level table
        table_data = _read.get_table_data(table_name, extschema, idl)

        if table_data is not None:
            config.update(table_data)

    # remove system uuid
    config[ops.constants.OVSDB_SCHEMA_SYSTEM_TABLE] = config[ops.constants.OVSDB_SCHEMA_SYSTEM_TABLE].values()[0]
    return config

def write(data, extschema, idl, txn):
    """Write a new configuration to OpenSwitch OVSDB database

    Args:
        data (dict): The new configuration represented as a Python
            dictionary object.
        extschema (opslib.RestSchema): This is the
            parsed extended-schema (vswitch.extschema) object.
        idl (ovs.db.idl.Idl): This is the IDL object that
            represents the OVSDB IDL.
        txn (ovs.db.idl.Transaction): OVSDB transaction object.

    Returns:
        (result, error) : A tuple containing the result of the transaction and
            error, if any, is returned
   """

    # dc.read returns config db with 'System' table
    # indexed to 'System' keyword. Replace it with
    # current database's System row UUID so that all
    # tables in 'data' are represented the same way

    system_uuid = idl.tables[ops.constants.OVSDB_SCHEMA_SYSTEM_TABLE].rows.keys()[0]
    data[ops.constants.OVSDB_SCHEMA_SYSTEM_TABLE] = {system_uuid:data[ops.constants.OVSDB_SCHEMA_SYSTEM_TABLE]}

    # iterate over all top-level tables i.e. root
    for table_name, tableschema in extschema.ovs_tables.iteritems():

        # iterate over non-children tables
        if extschema.ovs_tables[table_name].parent is not None:
            continue

        # set up the non-child table
        _write.setup_table(table_name, data, extschema, idl, txn)

    # iterate over all tables to fill in references
    for table_name, tableschema in extschema.ovs_tables.iteritems():

        if extschema.ovs_tables[table_name].parent is not None:
            continue

        _write.setup_references(table_name, data, extschema, idl)
    return txn.commit()
