# Full Declarative Configuration

## Contents
- [Overview](#overview)
- [Modules](#modules)
- [Usage](#usage)

### Overview
Declarative configuration  is used for reading and writing full configuration data into OVSDB.

```runconfig``` is the module  that provides the functionality to save a user-defined OpenSwitch full configuration to the OVSDB or to read the full configuration data from OVSDB.  Declarative Configuration is invoked by REST API's GET/PUT full configuration request(Please see example in Usage).

There are two types of configuration, the current "running" configuration and "startup" configuration. The running configuration does not persist across reboots, whereas startup configuration does.  When a configuration is "saved", such that it persists across reboots, it is stored into the "configuration" table in OVSDB (configtbl).

### Modules
```runconfig``` is part of  ```ops-restd``` repo. It has these modules:
```
runconfig
├── \__init__.py
├── runconfig.py
├── settings.py
├── declarativeconfig.py
├── validatoradapter.py
└── startupconfig.py
```

####startupconfig.py
````startupconfig.py``` is used to load the switch with the initial configuration on boot up.
OVSDB is not persisted across reboots, so it comes up initially empty except for the configurations table(configtbl). After the platform daemons have discovered all of the hardware present and populated the OVSDB with the relevant information for the hardware, the configuration daemon (cfgd) looks into configtbl to see if any saved configuration exists. cfgd looks for an entry of type startup. If a startup configuration is found it is applied over the rest of the tables, else cfgd notes that no configuration file was found

#### runconfig.py
```runconfig.py``` is a wrapper which invokes the read and write functions in ```declarativeconfig.py``` module.

#### declarativeconfig.py
 ```declarativeconfig.py``` is a module containing read and write functions which are invoked by ```runconfig.py```.
When user sends a GET request, the read function is invoked from REST handlers and works as follows: The function reads OVSDB, table by table and populates the JSON data(content of GET response) with all the columns that are of type configuration.
When user sends a PUT request, the write function is invoked and works as follows: For all top level tables, the entries are read from JSON data and populated to OVSDB table by table. All tables under top level table(i.e. children) are populated recursively. Immutable tables are ignored and rest of the tables are updated with user input configuration data. PUT is not an append but an overwrite operation, existing data is replaced by the provided input and  any missing fields in the input JSON data is treated as being removed and cleared from the OVSDB. Schema validations and custom validations are performed to catch erroneous configuration input and the erroneous input is rejected.

#### validatoradapter.py

```validatoradapter.py``` provides validations for resource creating, updating, and deleting. For more details please refer ```custom_validators_design.md```.

### Usage
- User can send a GET request with a url ```http://x.x.x.x:8091/rest/v1/system/full-configuration?type=running``` to get the running configuration of the switch.
-  User can give the full configuration data in the body of PUT request through REST API to update the OVSDB with the input configuration.

The PUT request data is in JSON data format. A basic example is as shown
```
{
    "table_name": {
        "column_name": "value",
        "column_name": "value"
    }
}
```
This input data can be constructed looking at the ```vswitch.extschema``` which is a JSON file with a list of table names, column names under the table and the relationship between the tables.
