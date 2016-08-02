#!/usr/bin/env python
# Copyright (C) 2015 Hewlett-Packard Enterprise Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import getopt
import json
import sys
import re
import string

import inflect
import xml.etree.ElementTree as ET

import ovs.dirs
from copy import deepcopy
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl


# Global variables
inflect_engine = inflect.engine()

# Schema constants
OVSDB_SCHEMA_CONFIG = 'configuration'
OVSDB_SCHEMA_STATS = 'statistics'
OVSDB_SCHEMA_STATUS = 'status'
OVSDB_CATEGORY_PERVALUE = 'per-value'
OVSDB_CATEGORY_FOLLOWS = 'follows'

# On demand fetched tables
FETCH_TYPE_PARTIAL = 0
FETCH_TYPE_FULL = 1
ON_DEMAND_FETCHED_TABLES = {
    "BGP_Route": FETCH_TYPE_PARTIAL,
    "BGP_Nexthop": FETCH_TYPE_PARTIAL,
    "Route": FETCH_TYPE_PARTIAL,
    "Nexthop": FETCH_TYPE_PARTIAL
}


# Convert name into all lower case and into plural (default) or singular format
def normalizeName(name, to_plural=True):
    lower_case = name.lower()
    # Assuming table names use underscore to link words
    words = string.split(lower_case, '_')

    if to_plural:
        words[-1] = inflect_engine.plural_noun(words[-1])
    else:
        words[-1] = inflect_engine.singular_noun(words[-1])

    return(string.join(words, '_'))


def extractColDesc(column_desc, loadDesc):
    if not loadDesc:
        return ""
    if column_desc is None:
        column_desc = ""
    # Remove unecessary tags at the beginning of each description
    if column_desc != "":
        column_desc = " ".join(column_desc.split())
    reg = '<column .*?>(.*)</column>'
    r = re.search(reg, column_desc)
    if r is None:
        return ""
    else:
        return str(r.group(1)).lstrip().rstrip()


class OVSColumn(object):
    """__init__() functions as the class constructor"""
    def __init__(self, table, col_name, type_, is_optional=True,
                 mutable=True, category=None, loadDesc=False):
        self.name = col_name

        # category type of this column
        self.category = category

        # is this column entry optional
        self.is_optional = is_optional

        # is this column modifiable after creation
        self.mutable = mutable

        base_key = type_.key
        base_value = type_.value

        # Possible values for keys only
        self.enum = base_key.enum

        self.type, self.rangeMin, self.rangeMax = self.process_type(base_key)

        self.value_type = None
        if base_value is not None:
            self.value_type, self.valueRangeMin, self.valueRangeMax = \
                self.process_type(base_value)

        # The number of instances
        self.is_dict = self.value_type is not None
        self.is_list = (not self.is_dict) and type_.n_max > 1
        self.n_max = type_.n_max
        self.n_min = type_.n_min

        self.kvs = {}
        columnDesc = self.parse_xml_rec(table.name, col_name, self.kvs, loadDesc)
        self.desc = extractColDesc(columnDesc, loadDesc)

    # Read the description for each column from XML source
    def parse_xml_rec(self, tableName, xmlColumn, kvs, loadDesc):
        columnDesc = " "
        if (tableName, xmlColumn) not in xml_column_dict.keys():
            return columnDesc
        columns = xml_column_dict[(tableName, xmlColumn)]
        for column in columns:
            if('keyname' in column.attrib):
                self.keyname = column.attrib['keyname']

            if ('key' not in column.attrib):
                columnDesc = ET.tostring(column, encoding='utf8',
                                         method='html')
                continue
            # When an attribute is of type string in schema file,
            # it may have detailed structure information in its
            # companion XML description, otherwise the parent
            # column's type is assumed.
            kvs[column.attrib['key']] = {}
            if ('type' in column.attrib):
                try:
                    typeData = json.loads(column.attrib['type'])
                except:
                    typeData = column.attrib['type']
                base_type = types.BaseType.from_json(typeData)
                type_, min_, max_ = self.process_type(base_type)
                enum = base_type.enum
            else:
                type_ = self.value_type
                min_ = self.valueRangeMin
                max_ = self.valueRangeMax
                enum = None

            kvs[column.attrib['key']]['type'] = type_
            kvs[column.attrib['key']]['rangeMin'] = min_
            kvs[column.attrib['key']]['rangeMax'] = max_
            kvs[column.attrib['key']]['enum'] = enum
            # Since there's no indication of optional in the XML schema,
            # it inherits its column's. Setting this so that eventually
            # it can be filled from info in the XML schema
            kvs[column.attrib['key']]['is_optional'] = self.is_optional

            key_desc = ET.tostring(column, encoding='utf8',
                                   method='html')
            kvs[column.attrib['key']]['desc'] = extractColDesc(key_desc, loadDesc)
        return columnDesc

    def process_type(self, base):
        type = base.type
        rangeMin = None
        rangeMax = None

        if type == types.StringType:

            if base.min_length is None:
                rangeMin = 0
            else:
                rangeMin = base.min_length

            if base.max_length is None:
                rangeMax = sys.maxint
            else:
                rangeMax = base.max_length

        elif type == types.UuidType:
            rangeMin = None
            rangeMax = None

        elif type != types.BooleanType:

            if base.min is None:
                rangeMin = 0
            else:
                rangeMin = base.min

            if base.max is None:
                rangeMax = sys.maxint
            else:
                rangeMax = base.max

        return (type, rangeMin, rangeMax)


class OVSReference(object):
    """__init__() functions as the class constructor"""
    def __init__(self, type_, relation='reference', mutable=True,
                 category=None):
        base_type = type_.key
        self.mutable = mutable

        # category type of this reference
        self.category = category

        # Name of the table being referenced
        self.kv_type = False
        if base_type.type != types.UuidType:
            # referenced table name must be in value part of KV pair
            self.kv_type = True
            self.kv_key_type = base_type.type
            base_type = type_.value
        self.ref_table = base_type.ref_table_name

        # Relationship of the referenced to the current table
        # one of child, parent or reference
        if relation == "child":
            self.relation = "child"
        elif relation == "parent":
            self.relation = "parent"
        elif relation == "reference":
            self.relation = "reference"
        else:
            raise error.Error("unknown table relationship %s" % relation)

        # The number of instances
        self.is_plural = (type_.n_max != 1)
        self.n_max = type_.n_max
        self.n_min = type_.n_min

        self.type = base_type.type


class OVSColumnCategory(object):
    def __init__(self, category):
        self.dynamic = False
        self.value = None
        self.validate(category)

        # Process category type
        if isinstance(category, dict):
            per_value_list = category.get(OVSDB_CATEGORY_PERVALUE,
                                          None)
            self.per_value = {}

            if per_value_list:
                for value_dict in per_value_list:
                    self.check_category(value_dict["category"])
                    self.per_value[value_dict["value"]] = \
                        value_dict["category"]

            self.follows = category.get(OVSDB_CATEGORY_FOLLOWS,
                                        None)
            self.value = OVSDB_SCHEMA_CONFIG
            self.dynamic = True

        elif isinstance(category, (str, unicode)):
            self.value = category

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        elif isinstance(other, (str, unicode)):
            return self.value == other
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def validate(self, category):
        if category:
            if isinstance(category, dict):
                if not (OVSDB_CATEGORY_PERVALUE in category
                        or OVSDB_CATEGORY_FOLLOWS in category):
                    raise error.Error("Unknown category object "
                                      "attributes")

            elif isinstance(category, (str, unicode)):
                self.check_category(category)
            else:
                raise error.Error("Unknown category type %s" % type(category))

    def check_category(self, category):
        if category not in [OVSDB_SCHEMA_CONFIG,
                            OVSDB_SCHEMA_STATS,
                            OVSDB_SCHEMA_STATUS]:
            raise error.Error("Unknown category: %s" % value)


class OVSTable(object):
    """__init__() functions as the class constructor"""
    def __init__(self, name, is_root, is_many=True):
        self.name = name
        self.plural_name = normalizeName(name)

        self.is_root = is_root

        # List of all column names
        self.columns = []

        # List of read-only column names
        self.readonly_columns = []

        # Is the table in plural form?
        self.is_many = is_many

        # Dictionary of configuration attributes (RW)
        # column name to OVSColumn object mapping
        self.config = {}

        # Copy of configuration attributes
        self.default_config = {}

        # Dictionary of status attributes (Read-only)
        # column name to OVSColumn object mapping
        self.status = {}

        # Dictionary of statistics attributes (Read-only)
        # column name to OVSColumn object mapping
        self.stats = {}

        # Dictionay with category that is an object type
        self.dynamic = {}

        # Parent table name
        self.parent = None

        # Child table list
        self.children = []

        # List of table referenced
        # table name to OVSReference object mapping
        self.references = {}

        # TODO: index columns are those columns that
        # OVSDB uses for indexing rows in a table.
        self.index_columns = None

        # TODO: indexes was introduced to create unique URIs for
        # resources. This is not always equal to index_columns
        # and is a source of confusion. This should be removed
        # eventually.
        self.indexes = None

    @staticmethod
    def from_json(json, name, loadDescription):
        parser = ovs.db.parser.Parser(json, "schema of table %s" % name)
        columns_json = parser.get("columns", [dict])
        mutable = parser.get_optional("mutable", [bool], True)
        is_root = parser.get_optional("isRoot", [bool], False)
        max_rows = parser.get_optional("maxRows", [int])
        indexes_json = parser.get_optional("indexes", [list], [[]])

        parser.finish()

        if max_rows is None:
            max_rows = sys.maxint
        elif max_rows <= 0:
            raise error.Error("maxRows must be at least 1", json)

        if not columns_json:
            raise error.Error("table must have at least one column", json)

        table = OVSTable(name, is_root, max_rows != 1)
        table.index_columns = indexes_json[0]

        for column_name, column_json in columns_json.iteritems():
            parser = ovs.db.parser.Parser(column_json, "column %s" % name)
            # The category can be a str or a object. The object inside can
            # have the following keys:
            # per-value: matches the possible value with the desired category
            # follows: Reference to the column used to determine the column
            #          category
            category = OVSColumnCategory(parser.get_optional("category",
                                                             [str, unicode,
                                                              dict]))
            relationship = parser.get_optional("relationship", [str, unicode])
            mutable = parser.get_optional("mutable", [bool], True)
            ephemeral = parser.get_optional("ephemeral", [bool], False)
            type_ = types.Type.from_json(parser.get("type", [dict, str,
                                                             unicode]))
            parser.finish()

            is_column_skipped = False
            is_readonly_column = False
            is_optional = False
            if isinstance(column_json['type'], dict):
                if ('min' in column_json['type'] and
                        column_json['type']['min'] == 0):
                    is_optional = True

            # An attribute will be able to get marked with relationship
            # and category tags simultaneously. We are utilizing the
            # new form of tagging as a second step.
            # For now, we are using only one tag.
            if relationship == "1:m":
                table.references[column_name] = OVSReference(type_, "child",
                                                             mutable, category)
                table.references[column_name].column = OVSColumn(table,
                                                                 column_name,
                                                                 type_,
                                                                 True,
                                                                 mutable,
                                                                 category,
                                                                 loadDescription)
            elif relationship == "m:1":
                table.references[column_name] = OVSReference(type_, "parent",
                                                             mutable, category)
            elif relationship == "reference":
                _mutable = mutable if category == 'configuration' else False
                table.references[column_name] = OVSReference(type_,
                                                             "reference",
                                                             _mutable,
                                                             category)
            elif category == "configuration":
                if name in ON_DEMAND_FETCHED_TABLES and \
                     ON_DEMAND_FETCHED_TABLES[name] == FETCH_TYPE_FULL:
                     is_readonly_column = True

                table.config[column_name] = OVSColumn(table, column_name,
                                                      type_, is_optional,
                                                      mutable, category,
                                                      loadDescription)
            elif category == "status":
                is_readonly_column = True
                table.status[column_name] = OVSColumn(table, column_name,
                                                      type_, is_optional,
                                                      True, category,
                                                      loadDescription)
            elif category == "statistics":
                is_readonly_column = True
                table.stats[column_name] = OVSColumn(table, column_name,
                                                     type_, is_optional,
                                                     True, category,
                                                     loadDescription)

            else:
                # Skip columns that do not have a handled relationship or
                # category.
                is_column_skipped = True

            # Add to the array the name of the dynamic column
            if category.dynamic:
                table.dynamic[column_name] = category

            # If the column is readonly, check if it is an index. Indexes
            # should not be registered as readonly columns in the case of a
            # partial fetching. In full fetch, no columns are subscribed to, so
            # consider all columns as readonly columns
            if name in ON_DEMAND_FETCHED_TABLES and is_readonly_column:
                if ON_DEMAND_FETCHED_TABLES[name] == FETCH_TYPE_PARTIAL and \
                     column_name in table.index_columns:
                    pass
                else:
                    table.readonly_columns.append(str(column_name))

            if not is_column_skipped:
                table.columns.append(str(column_name))

        # deepcopy of config attributes to prevent modification
        # of config attributes when updating dynamic categories
        table.default_config = deepcopy(table.config)

        # Validate dynamic categories consistency
        for column_name, category in table.dynamic.iteritems():
            if category.follows is not None\
               and category.follows not in table.columns:
                raise error.Error("Follows column '%s'"
                                  "doesn't exists at table '%s'"
                                  % (category.follows, name))

        # TODO: indexes should be removed eventually
        table.indexes = []
        if not table.index_columns:
            table.indexes = ['uuid']
        else:
            for item in table.index_columns:
                if item in table.references and\
                        table.references[item].relation == 'parent':
                    continue
                table.indexes.append(item)

        return table


class RESTSchema(object):
    """Schema for REST interface from an OVSDB database."""

    def __init__(self, name, version, tables):
        self.name = name
        self.version = version
        # A dictionary of table name to OVSTable object mappings
        self.ovs_tables = tables

        # get a table name map for all references
        self.reference_map = {}
        for table in self.ovs_tables:
            for k, v in self.ovs_tables[table].references.iteritems():
                if k not in self.reference_map:
                    self.reference_map[k] = v.ref_table

        # tables that has the refereces to one table
        self.references_table_map = {}
        for table in self.ovs_tables:
            tables_references = get_references_tables(self, table)
            self.references_table_map[table] = tables_references

        # get a plural name map for all tables
        self.plural_name_map = {}
        for table in self.ovs_tables.itervalues():
            self.plural_name_map[table.plural_name] = table.name

    @staticmethod
    def from_json(json, loadDescription):
        parser = ovs.db.parser.Parser(json, "extended OVSDB schema")
        name = parser.get("name", ['id'])
        version = parser.get_optional("version", [str, unicode])
        tablesJson = parser.get("tables", [dict])
        parser.finish()

        if (version is not None and
                not re.match('[0-9]+\.[0-9]+\.[0-9]+$', version)):
                raise error.Error('schema version "%s" not in format x.y.z'
                                  % version)

        tables = {}
        for tableName, tableJson in tablesJson.iteritems():
            tables[tableName] = OVSTable.from_json(tableJson, tableName,
                loadDescription)

        # Backfill the parent/child relationship info, mostly for
        # parent pointers which cannot be handled in place.
        for tableName, table in tables.iteritems():
            for columnName, column in table.references.iteritems():
                if column.relation == "child":
                    table.children.append(columnName)
                    if tables[column.ref_table].parent is None:
                        tables[column.ref_table].parent = tableName
                elif column.relation == "parent":
                    if tableName not in tables[column.ref_table].children:
                        tables[column.ref_table].children.append(tableName)
                    table.parent = column.ref_table

        return RESTSchema(name, version, tables)


def get_references_tables(schema, ref_table):
    table_references = {}
    for table in schema.ovs_tables:
        columns = []
        references = schema.ovs_tables[table].references
        for column_name, reference in references.iteritems():
            if reference.ref_table == ref_table:
                columns.append(column_name)
        if columns:
            table_references[table] = columns
    return table_references


def is_immutable(table, schema):

    """
    A table is considered IMMUTABLE if REST API cannot add or
    delete a row from it
    """
    table_schema = schema.ovs_tables[table]

    # ROOT table
    if table_schema.is_root:
        # CASE 1: if there are no indices, a root table is considered
        #         IMMUTABLE for REST API
        # CASE 2: if there is at least one index of category 'configuration',
        #         a root table is considered MUTABLE for REST API

        # NOTE: an immutable table can still be modified by other daemons
        # running on  the switch. For example, system daemon can modify
        # FAN table although REST cannot
        return not _has_config_index(table, schema)

    else:

        # top level table e.g. Port
        if table_schema.parent is None:
            return not _has_config_index(table, schema)
        else:
            # child e.g. Bridge
            # check if the reference in 'parent' is of category 'configuration'
            parent = table_schema.parent
            parent_schema = schema.ovs_tables[parent]
            children = parent_schema.children

            regular_children = []
            for item in children:
                if item in parent_schema.references:
                    regular_children.append(item)

            ref = None
            if table not in parent_schema.children:
                for item in regular_children:
                    if parent_schema.references[item].ref_table == table:
                        ref = item
                        break

                if parent_schema.references[ref].category == 'configuration':
                    return False

            else:
                # back children
                return not _has_config_index(table, schema)

    return True


def _has_config_index(table, schema):
    """
    return True if table has at least one index column of category
    configuration
    """
    for index in schema.ovs_tables[table].index_columns:
        if index in schema.ovs_tables[table].config:
            return True
        elif index in schema.ovs_tables[table].references:
            if schema.ovs_tables[table].references[index].category == \
                    'configuration':
                return True

    # no indices or no index columns with category configuration
    return False

def parse_columns(node, column):
    if column.tag == 'column':
        key = (node.attrib['name'], column.attrib['name'])
        if key not in xml_column_dict:
            xml_column_dict[key] = []
        xml_column_dict[key].append(column)

    elif column.tag == 'group':
        for group_column in column.getchildren():
            parse_columns(node, group_column)



def parseSchema(schemaFile, title=None, version=None, loadDescription=False):
    # Initialize a global variable here
    global xml_column_dict


    xml_column_dict={}
    # Assume the companion XML file and schema file differ only in extension
    # for their names (.extschema vs .xml)
    xmlFile = schemaFile[:-len("extschema")] + "xml"
    with open(xmlFile, 'rt') as f:
        xml_tree = ET.parse(f)

    for node in xml_tree.iter():
        if node.tag != 'table':
            continue
        for column in node.getchildren():
            parse_columns(node, column)

    schema = RESTSchema.from_json(ovs.json.from_file(schemaFile), loadDescription)

    if title is None:
        title = schema.name
    if version is None:
        version = "UNKNOWN"

    # add mutable flag to OVSTable
    for name, table in schema.ovs_tables.iteritems():
        table.mutable = not is_immutable(name, schema)

    return schema


def usage():
    print """\
%(argv0)s: REST API meta schema file parser
Parse the meta schema file based on OVSDB schema to obtain category and
relation information for each REST resource.
usage: %(argv0)s [OPTIONS] SCHEMA
where SCHEMA is an extended OVSDB schema in JSON format.

The following options are also available:
  --title=TITLE               use TITLE as title instead of schema name
  --version=VERSION           use VERSION to display on document footer
  -h, --help                  display this help message\
""" % {'argv0': argv0}
    sys.exit(0)


if __name__ == "__main__":
    try:
        try:
            options, args = getopt.gnu_getopt(sys.argv[1:], 'h',
                                              ['title=', 'version=', 'help'])
        except getopt.GetoptError, geo:
            sys.stderr.write("%s: %s\n" % (argv0, geo.msg))
            sys.exit(1)

        title = None
        version = None
        for key, value in options:
            if key == '--title':
                title = value
            elif key == '--version':
                version = value
            elif key in ['-h', '--help']:
                usage()
            else:
                sys.exit(0)

        if len(args) != 1:
            sys.stderr.write("Exactly 1 non-option arguments required "
                             "(use --help for help)\n")
            sys.exit(1)

        schema = parseSchema(args[0])

        for table_name, table in schema.ovs_tables.iteritems():
            print("Table %s: " % table_name)
            print("Parent  = %s" % table.parent)
            print("Configuration attributes: ")
            for column_name, column in table.config.iteritems():
                print("Col name = %s: %s" % (column_name,
                      "plural" if column.is_list else "singular"))
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" % (column.type,
                      column.rangeMin, column.rangeMax))
                print("key enum = %s" % column.enum)
                print("key kvs = %s" % column.kvs)
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" %
                          (column.value_type,
                           column.valueRangeMin,
                           column.valueRangeMax))
            print("Status attributes: ")
            for column_name, column in table.status.iteritems():
                print("Col name = %s: %s" % (column_name,
                      "plural" if column.is_list else "singular"))
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" %
                      (column.type, column.rangeMin, column.rangeMax))
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" %
                          (column.value_type,
                           column.valueRangeMin,
                           column.valueRangeMax))
            print("Stats attributes: ")
            for column_name, column in table.stats.iteritems():
                print("Col name = %s: %s" % (column_name,
                      "plural" if column.is_list else "singular"))
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" %
                      (column.type, column.rangeMin, column.rangeMax))
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" %
                          (column.value_type,
                           column.valueRangeMin,
                           column.valueRangeMax))
            print("Subresources: ")
            for column_name, column in table.references.iteritems():
                print("Col name = %s: %s, %s" % (column_name, column.relation,
                      "plural" if column.is_plural else "singular"))
            print("\n")

    except error.Error, e:
        sys.stderr.write("%s\n" % e.msg)
        sys.exit(1)

# Local variables:
# mode: python
# End:
