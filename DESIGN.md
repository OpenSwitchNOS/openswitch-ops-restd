OpenSwitch RESTful API to OVSDB
===================

Overview
------------
OpenSwitch provides a <a href="http://www.tornadoweb.org/en/stable/">Tornado</a> framework based application to access **OVSDB** using RESTful APIs. ops-restd module provides all the necessary python packages required to add, delete, modify tables in the OVSDB database using ```HTTP``` methods, ```GET, POST, PUT and DELETE```.

Modules
------
```ops-restd``` consists of the following modules.

 - **opslib** - Interface to the OVSDB schema and OpenSwitch extended schema.
 - **opsrest** - Tornado application to provide RESTful access to OVSDB.
 - **runconfig**- Module to load a user defined OVSDB configuration.

**opslib**

```opslib``` modules provides the interface to OpenSwitch's vswitch.extschema vswitch.xml files and provides tools to automatically generated documentation of all supported APIs. The database schema and the relationship between various tables is defined by these two files and opslib captures this information. ```opsrest``` uses this information to verify the REST APIs and allow or deny access to the resources (tables) in the database. This module is also used to generate the <a href="http://swagger.io/">Swagger</a> documentation of the APIs that are supported by ```ops-restd```

> opslib
├── apidocgen.py (**creates Swagger documentation of supported APIs**)
├── \__init__.py
└── restparser.py (**interface to vswitch.extschema and vswitch.xml**)


**opsrest**

```opsrest``` is the implementation of the RESTful API application and does the following:

 - Maintains a persistent connection with the OVSDB server.
 - Actively listens to notifications from the OVSDB server to monitor changes to the OVSDB.
 - Asynchronously accepts and serves incoming HTTP requests.
 - Provides GET/POST/PUT/DELETE HTTP methods to read/add/modify/delete resources to/from the OVSDB database.
 - Provides authentication and authorization feature for the APIs.


```
opsrest
├── application.py
├── constants.py
├── delete.py
├── get.py
├── handlers
│   ├── base.py
│   ├── config.py
│   └── \__init__.py
├── \__init__.py
├── manager.py
├── parse.py
├── post.py
├── put.py
├── resource.py
├── settings.py
├── transaction.py
├── urls.py
├── utils
│   ├── \__init__.py
│   └── utils.py
└── verify.py
```
**runconfig**

This Python module provides functionality to save a user defined OpenSwitch configuration to OVSDB. ```opslib``` and ```ops-cli``` use this module to allow REST and CLI access to this feature.

```
runconfig
├── \__init__.py
├── runconfig.py
├── settings.py
└── startupconfig.py
```

Design
------------------
```ops-restd``` uses Tornado's non-blocking feature to implement an asynchronous application that simultaneously accepts more than one HTTP connection and performs non-blocking read/write to OVSDB. ```Python``` class ```OvsdbConnectionManager``` found in ```opsrest/manager.py``` provides all the connection, read, write related features with OVSDB.

```OvsdbConnectionManager``` maintains a list of all OVSDB transactions in a ```OvsdbTransactionList``` object. Each transaction corresponds to a write request to the database.
```
            if self.transactions is None:
                self.transactions = OvsdbTransactionList()
```
On every <a href="http://tornado.readthedocs.org/en/latest/ioloop.html/">IOLoop</a> iteration the transactions in this list are checked to their current status. If a transaction is ```INCOMPLETE```, we call ```commit``` on it and in all other cases we remove it from the transaction list and notify the method that invoked it.
```
    def check_transactions(self):

        for item in self.transactions.txn_list:
            item.commit()

        count = 0
        for item in self.transactions.txn_list:

            # TODO: Handle all states
            if item.status is not INCOMPLETE:
                self.transactions.txn_list.pop(count)
                item.event.set()
            else:
                count += 1
```
