
[Standard REST API] Test Cases
==============================

## Contents

- [REST full declarative configuration](#rest-full-declarative-configuration)
- [REST Selector validation](#rest-selector-validation)

## REST full declarative configuration
### Objective
The objective of the test case is to verify if the user configuration is set in the OVSDB.

### Requirements
The requirements for this test case are:

- OpenSwitch
- Ubuntu Workstation

### Setup
#### Topology diagram
```ditaa
+---------------+                 +---------------+
|               |                 |    Ubuntu     |
|  OpenSwitch   |eth0---------eth1|               |
|               |      lnk01      |  Workstation  |
+---------------+                 +---------------+
```

### Description
This test case verifies if the configuration was set correctly by comparing user configuration (input) with the output of OVSDB read.

 1. Connect OpenSwitch to the Ubuntu workstation as shown in the topology diagram.
 2. Configure the IPV4 address on the switch management interfaces.
 3. Configure the IPV4 address on the Ubuntu workstation.
 4. This script validates if the input configuration is updated correctly in the OVSDB by comparing output configuration (read from OVSDB after write) with user input configuration.

### Test result criteria
#### Test pass criteria
The test case passes if the input configuration matches the output configuration (read from OVSDB after write).

#### Test fail criteria
The test case is failing if the input configuration does not match the output configuration (read from OVSDB after write).

## REST Selector validation

### Objective
The objective of the test case is to verify the *selector* query argument

### Requirements
The requirements for this test case are:

- OpenSwitch
- Ubuntu Workstation

### Setup
#### Topology diagram
```ditaa
+---------------+                 +---------------+
|               |                 |    Ubuntu     |
|  OpenSwitch   |eth0---------eth1|               |
|               |      lnk01      |  Workstation  |
+---------------+                 +---------------+
```

### Description
This test case validates the *selector* query parameter through the standard REST API GET method.

1. Verify if response has a `400 BAD REQUEST` HTTP response status code by using a invalid selector
   parameter in combination with the *depth* parameter.
    a. Execute the GET request over `/rest/v1/system/interfaces?selector=invalid;depth=1`
    b. Verify if the HTTP response is `400 BAD REQUEST`.

2. Verify if response has a `200 OK` HTTP response status code by using a *configuration* selector
   parameter in combination with the *depth* parameter.
    a. Execute the GET request over `/rest/v1/system/interfaces?selector=configuration;depth=1`
    b. Verify if the HTTP response is `200 OK`.

3. Verify if response has a `200 OK` HTTP response status code by using a *status* selector
   parameter in combination with the *depth* parameter.
    a. Execute the GET request over `/rest/v1/system/interfaces?selector=status;depth=1`
    b. Verify if the HTTP response is `200 OK`.

4. Verify if response has a `200 OK` HTTP response status code by using a *statistics* selector
   parameter in combination with the *depth* parameter.
    a. Execute the GET request over `/rest/v1/system/interfaces?selector=statistics;depth=1`
    b. Verify if the HTTP response is `200 OK`.

### Test result criteria
#### Test pass criteria

This test passes by meeting the following criteria:

- Querying a interface list with an invalid *selector* parameter returns a `400 BAD REQUEST`
- Querying a interface list with an valid *selector* parameter returns a `200 OK`

#### Test fail criteria

This test fails when:

- Querying a interface list with an invalid *selector* parameter returns anything other than
  `400 BAD REQUEST` HTTP response
- Querying a interface list with an valid *selector* parameter returns anything other than
  `200 OK` HTTP response
