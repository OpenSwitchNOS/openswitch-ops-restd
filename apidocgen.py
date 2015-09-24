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

import xml.etree.ElementTree as ET

import ovs.dirs
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl

from opslib.restparser import OVSColumn
from opslib.restparser import OVSReference
from opslib.restparser import OVSTable
from opslib.restparser import RESTSchema
from opslib.restparser import normalizeName
from opslib.restparser import parseSchema


def addCommonResponse(responses):
    response = {}
    response["description"] = "Unauthorized"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["401"] = response

    response = {}
    response["description"] = "Forbidden"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["403"] = response

    response = {}
    response["description"] = "Not found"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["404"] = response

    response = {}
    response["description"] = "Method not allowed"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["405"] = response

    response = {}
    response["description"] = "Internal server error"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["500"] = response

    response = {}
    response["description"] = "Service unavailable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["503"] = response


def addGetResponse(responses):
    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    addCommonResponse(responses)


def addPostResponse(responses):
    response = {}
    response["description"] = "Created"
    schema = {}
    schema["$ref"] = "#/definitions/Resource"
    response["schema"] = schema
    responses["201"] = response

    response = {}
    response["description"] = "Bad request"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["400"] = response

    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    response = {}
    response["description"] = "Unsupported media type"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["415"] = response

    addCommonResponse(responses)


def addPutResponse(responses):
    response = {}
    response["description"] = "OK"
    responses["200"] = response

    response = {}
    response["description"] = "Bad request"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["400"] = response

    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    response = {}
    response["description"] = "Unsupported media type"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["415"] = response

    addCommonResponse(responses)


def addDeleteResponse(responses):
    response = {}
    response["description"] = "Resource deleted"
    responses["204"] = response

    addCommonResponse(responses)


#
# Pass in chain of parent resources on URI path
#
def genCoreParams(table, parent_plurality, is_plural = True):
    depth = len(parent_plurality)

    params = []
    for level in range(depth):
        if parent_plurality[level]:
            param = {}
            param["name"] = "p"*(depth-level) + "id"
            param["in"] = "path"
            param["description"] = "parent resource id"
            param["required"] = True
            param["type"] = "string"
            params.append(param)

    if is_plural:
        param = {}
        param["name"] = "id"
        param["in"] = "path"
        param["description"] = "resource id"
        param["required"] = True
        param["type"] = "string"
        params.append(param)

    return params


def genGetResource(table, parent_plurality, is_plural):
    op = {}
    op["summary"] = "Get operation"
    op["description"] = "Get a list of resources"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, is_plural)
    if params:
        op["parameters"] = params

    responses = {}
    response = {}
    response["description"] = "OK"
    schema = {}
    schema["type"] = "array"
    item = {}
    item["description"] = "Resource URI"
    item["$ref"] = "#/definitions/Resource"
    schema["items"] = item
    schema["description"] = "A list of URIs"
    response["schema"] = schema
    responses["200"] = response

    addGetResponse(responses)
    op["responses"] = responses

    return op


def genPostResource(table, parent_plurality, is_plural):
    op = {}
    op["summary"] = "Post operation"
    op["description"] = "Create a new resource instance"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, is_plural)
    param = {}
    param["name"] = "data"
    param["in"] = "body"
    param["description"] = "data"
    param["required"] = True

    if table.parent is None:
        # For referenced resource
        param["schema"] = {'$ref': "#/definitions/"+table.name+"ConfigReferenced"}
    else:
        param["schema"] = {'$ref': "#/definitions/"+table.name+"ConfigOnly"}

    params.append(param)
    op["parameters"] = params

    responses = {}
    addPostResponse(responses)
    op["responses"] = responses

    return op


def genGetInstance(table, parent_plurality, is_plural):
    if table.config or table.status or table.stats:
        op = {}
        op["summary"] = "Get operation"
        op["description"] = "Get a set of attributes"
        op["tags"] = [table.name]

        params = genCoreParams(table, parent_plurality, is_plural)
        param = {}
        param["name"] = "selector"
        param["in"] = "query"
        param["description"] = "select from config, status or stats, default to all"
        param["required"] = False
        param["type"] = "string"
        params.append(param)
        op["parameters"] = params

        responses = {}
        response = {}
        response["description"] = "OK"
        response["schema"] = {'$ref': "#/definitions/"+table.name+"All"}
        responses["200"] = response

        addGetResponse(responses)
        op["responses"] = responses

        return op


def genPutInstance(table, parent_plurality, is_plural):
    if table.config:
        op = {}
        op["summary"] = "Put operation"
        op["description"] = "Update configuration"
        op["tags"] = [table.name]

        params = genCoreParams(table, parent_plurality, is_plural)
        param = {}
        param["name"] = "data"
        param["in"] = "body"
        param["description"] = "configuration"
        param["required"] = True
        param["schema"] = {'$ref': "#/definitions/"+table.name+"ConfigOnly"}
        params.append(param)
        op["parameters"] = params

        responses = {}
        addPutResponse(responses)
        op["responses"] = responses

        return op


def genDelInstance(table, parent_plurality, is_plural):
    op = {}
    op["summary"] = "Delete operation"
    op["description"] = "Delete a resource instance"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, is_plural)
    if params:
        op["parameters"] = params

    responses = {}
    addDeleteResponse(responses)
    op["responses"] = responses

    return op


# Generate definition for a given base type
def genBaseType(type, min, max, desc):
    item = {}
    if type == types.IntegerType:
        item["type"] = "integer"
        if min != None and min !=0:
            item["minimum"] = min
        if max != None and max != sys.maxint:
            item["maximum"] = max
    elif type == types.RealType:
        item["type"] = "real"
        if min != None and min != 0:
            item["minimum"] = min
        if max != None and max != sys.maxint:
            item["maximum"] = max
    elif type == types.BooleanType:
        item["type"] = "boolean"
    elif type == types.StringType:
        item["type"] = "string"
        if min != None and min != 0:
            item["minLength"] = min
        if max != None and max != sys.maxint:
            item["maxLength"] = max
    else:
        raise error.Error("Unexpected attribute type " + type)

    item["description"] = desc

    return item


# Generate definition for a column in a table
def genDefinition(table_name, col, definitions):
    properties = {}
    if col.is_dict and col.enum:
        # Key-Value type
        for key in col.enum:
            definition = {}
            # keys specified in schema file are all of string type
            definition["type"] = "string"
            properties[key] = definition

    if col.kvs:
        for key, detail in col.kvs.iteritems():
            if 'type' in detail.keys():
                type = detail['type']
            else:
                type = col.type
            if 'rangeMin' in detail.keys():
                min = detail['rangeMin']
            else:
                min = col.rangeMin
            if 'rangeMax' in detail.keys():
                max = detail['rangeMax']
            else:
                max = col.rangeMax
            if 'desc' in detail.keys():
                desc = detail['desc']
            else:
                desc = ""
            properties[key] = genBaseType(type, min, max, desc)

    if properties:
        definitions[table_name + "-" + col.name + "-KV"] = {"properties": properties}

        sub = {}
        sub["$ref"] = "#/definitions/" + table_name + "-" + col.name + "-KV"
        sub["description"] = "Key-Value pairs for " + col.name
        return sub
    else:
        # simple attributes
        return genBaseType(col.type, col.rangeMin, col.rangeMax, col.desc)


def getDefinition(table, definitions):
    properties = {}
    for colName, col in table.config.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    definitions[table.name + "Config"] = {"properties": properties}

    properties = {}
    for colName, col in table.status.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    definitions[table.name + "Status"] = {"properties": properties}

    properties = {}
    for colName, col in table.stats.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    definitions[table.name + "Stats"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Status"
    sub["description"] = "Status of " + table.name
    properties["status"] = sub
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Stats"
    sub["description"] = "Statistics of " + table.name
    properties["statistics"] = sub

    definitions[table.name + "All"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub

    definitions[table.name + "ConfigOnly"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub

    sub = {}
    sub["type"] = "array"
    sub["description"] = "A list of reference points"
    item = {}
    item["$ref"] = "#/definitions/ReferencedBy"
    sub["items"] = item
    properties["referenced_by"] = sub

    definitions[table.name + "ConfigReferenced"] = {"properties": properties}


def genAPI(paths, definitions, schema, table, resource_name, parent, parents, parent_plurality):
    prefix = "/system"
    depth = len(parents)
    for index, ancestor in enumerate(parents):
        prefix = prefix + "/" + ancestor
        if parent_plurality[index]:
            idname = "{" + "p"*(depth - index) + "id}"
            prefix = prefix + "/" + idname

    # Parentless resources always have multiple instances
    if resource_name is None:
        # system table
        is_plural = False
    elif parent is None:
        is_plural = True
    elif resource_name not in parent.references:
        # parent relation always have multiple children
        is_plural = True
    else:
        is_plural = parent.references[resource_name].is_plural

    if resource_name is not None:
        path = prefix + "/" + resource_name
    else:
        path = prefix

    ops = {}
    if is_plural:
        op = genGetResource(table, parent_plurality, False)
        if op is not None:
            ops["get"] = op
        op = genPostResource(table, parent_plurality, False)
        if op is not None:
            ops["post"] = op
    else:
        op = genGetInstance(table, parent_plurality, is_plural)
        if op is not None:
            ops["get"] = op
        op = genPutInstance(table, parent_plurality, is_plural)
        if op is not None:
            ops["put"] = op
    paths[path] = ops

    if is_plural:
        path = path + "/{id}"
        ops = {}
        op = genGetInstance(table, parent_plurality, is_plural)
        if op is not None:
            ops["get"] = op
        op = genPutInstance(table, parent_plurality, is_plural)
        if op is not None:
            ops["put"] = op
        op = genDelInstance(table, parent_plurality, is_plural)
        if op is not None:
            ops["delete"] = op
        paths[path] = ops

    getDefinition(table, definitions)

    # Stop for system resource
    if resource_name is None:
        return

    # Recursive into next level resources
    for col_name in table.references:
        child_name = table.references[col_name].ref_table
        child_table = schema.ovs_tables[child_name]
        if col_name in table.children:
            # True child resources
            parents.append(resource_name)
            parent_plurality.append(is_plural)
            genAPI(paths, definitions, schema, child_table, col_name, table, parents, parent_plurality)
            parents.pop()
            parent_plurality.pop()
        elif table.references[col_name].relation == "parent":
            continue
        else:
            # Referenced resources (no operation exposed)
            continue

    # For child resources declared with "parent" relationship
    for col_name in table.children:
        if col_name in table.references:
            # Processed already
            continue

        # Use plural form of the resource name in URI
        child_table = schema.ovs_tables[col_name]
        child_name = normalizeName(col_name)
        parents.append(resource_name)
        parent_plurality.append(is_plural)
        genAPI(paths, definitions, schema, child_table, child_name, table, parents, parent_plurality)
        parents.pop()
        parent_plurality.pop()


def getFullAPI(schema):
    api = {}
    api["swagger"] = "2.0"

    info = {}
    info["title"] = "OpenSwitch REST API"
    info["description"] = "REST interface for management plane"
    info["version"] = "1.0.0"
    api["info"] = info

    api["host"] = ""
    # Should be changed to use https instead
    api["schemes"] = ["http"]
    api["basePath"] = "/rest/v1"
    api["produces"] = ["application/json"]

    paths = {}
    definitions = {}

    # Special treat /system resource
    systemTable = schema.ovs_tables["System"]
    parents = []
    parent_plurality = []
    genAPI(paths, definitions, schema, systemTable, None, None, parents, parent_plurality)

    # Top-level tables exposed in system table
    for col_name in systemTable.references:
        name = systemTable.references[col_name].ref_table
        table = schema.ovs_tables[name]

        if col_name in systemTable.children:
            # True child resources
            parents = []
            parent_plurality = []
            genAPI(paths, definitions, schema, table, col_name, systemTable, parents, parent_plurality)
        else:
            # Referenced resources (no operation exposed)
            continue

    # Put referenced resources at the top level
    for table_name, table in schema.ovs_tables.iteritems():
        # Skipping those that are not top-level resources
        if table.parent is not None:
            continue
        # Skipping those that are not referenced
        if table_name not in schema.reference_map.values():
            continue

        parents = []
        parent_plurality = []
        # Use plural form of the resource name in the URI
        genAPI(paths, definitions, schema, table, table.plural_name, None, parents, parent_plurality)

    api["paths"] = paths

    properties = {}
    properties["message"] = {"type": "string"}
    definitions["Error"] = {"properties": properties}

    definition = {}
    definition["type"] = "string"
    definition["description"] = "Resource URI"
    definitions["Resource"] = definition

    properties = {}
    definition = {}
    definition["type"] = "string"
    definition["description"] = "URI of the resource making the reference"
    properties["uri"] = definition
    definition = {}
    definition["type"] = "array"
    definition["description"] = "A list of reference points, can be empty for default"
    items = {}
    items["type"] = "string"
    definition["items"] = items
    properties["attributes"] = definition
    definitions["ReferencedBy"] = {"properties": properties}

    api["definitions"] = definitions

    return api


def docGen(schemaFile, xmlFile, title=None, version=None):
    schema = parseSchema(schemaFile)

    # Special treat System table as /system resource
    schema.ovs_tables["System"] = schema.ovs_tables.pop("System")
    schema.ovs_tables["System"].name = "System"

    api = getFullAPI(schema)
    return json.dumps(api, sort_keys=True, indent=4)


def usage():
    print """\
%(argv0)s: REST API documentation generator
Parse the meta schema file based on OVSDB schema together with its
accompanying XML documentation file to generate REST API YAML file
for rendering through swagger.
usage: %(argv0)s [OPTIONS] SCHEMA XML
where SCHEMA is an extended OVSDB schema in JSON format
  and XML is its accompanying documentation in XML format.

The following options are also available:
  --title=TITLE               use TITLE as title instead of schema name
  --version=VERSION           use VERSION to override
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

        if len(args) != 2:
            sys.stderr.write("Exactly 2 non-option arguments required "
                             "(use --help for help)\n")
            sys.exit(1)

        s = docGen(args[0], args[1], title, version)
        print s

    except error.Error, e:
        sys.stderr.write("%s\n" % e.msg)
        sys.exit(1)

# Local variables:
# mode: python
# End:
