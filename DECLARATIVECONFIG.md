# Full Declarative Configuration

## Contents
- [Overview](#overview)
- [Modules](#modules)
- [Modules](#modules)
- [How to use](#how-to-use)


### Overview
Declarative configuration  is used for writing and reading from OVSDB. The ```runconfig``` is a module  that provides the functionality to save a user-defined OpenSwitch configuration to the OVSDB or to read the configuration data from OVSDB.  This can be used through REST API's GET/PUT request or independently.

### Modules
```runconfig``` is part of  ```ops-restd``` repo. It has the below modules:
```
runconfig
├── \__init__.py
├── runconfig.py(**Invokes read/write in declarativeconfig.py based on GET/PUT request**)
├── settings.py
├── declarativeconfig.py(**Modules to read from and write to OVSDB**)
├── validatoradapter.py(**Provides validations for resource creating, updating, and deleting**)
└── startupconfig.py
```

### Implementation Details
The ```runconfig``` module takes user configuration and updates the OVSDB with the user input configuration:

 - The read and write modules in ```declarativeconfig.py``` are invoked when the GET or PUT request is sent from the user through REST API
 - For GET request, the read function is invoked from REST handlers and works as follows: The function reads OVSDB table by table and populates the JSON data(content of GET response) with all the columns that are of type configuration.
 - For PUT request, the write function is invoked and works as follows: For all top level tables, the entries are read from JSON data and populated to OVSDB table by table. We fill all tables under top level table(i.e. children) recursively. Immutable tables are ignored and rest of the tables are updated with user input configuration data.

### How To Use
- User can send a GET request with a url http://x.x.x.x:8091/rest/v1/system/full-configuration?type=running to get the running configuration of the switch.
-  User can give the full configuration data as part of PUT request through REST API to update the OVSDB with the input configuration.
