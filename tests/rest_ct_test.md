[Standard REST API] Test Cases
==============================

 [TOC]

##  REST Full Declarative configuration ##
### Objective ###
The objective of the test case is to verify if the user configuration was set.
### Requirements ###
The requirements for this test case are:
 - OpenSwitch.
 - Ubuntu Workstation.
### Setup ###
#### Topology Diagram ####
+---------------+                 +---------------+
|               |                 |    Ubuntu     |
|  OpenSwitch   |eth0---------eth1|               |
|               |      lnk01      |  Workstation  |
+---------------+                 +---------------+
### Description ###
This test case verifies if the configuration was set correctly by comparing user config(input) with the output of ovsdb read.

> **STEPS:**

> - Connect the OpenSwitch to Ubuntu workstation as shown in the topology diagram.
> - Configure the IPV4 address on the switch management interfaces.
> - Configure the IPV4 address on the Ubuntu workstation.
> - This script validates if the input configuration is updated correctly in the OVSDB by
    comparing user input config with output config(read from OVSDB after write).

### Test Result Criteria ###
#### Test Pass Criteria ####
The test case is pass if the input config matches the output config(read from OVSDB after write)".
#### Test Fail Criteria ####
The test case is fail if the input config does not match the output config(read from OVSDB after write).
