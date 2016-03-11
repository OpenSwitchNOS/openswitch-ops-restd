
[Standard REST API] Test Cases
==============================

## Contents

- [REST full declarative configuration](#rest-full-declarative-configuration)
- [REST WebSocket Events](#rest-websocket-events)
  - [Subscribe to row for specific column changes](#subscribe-to-row-for-specific-column-changes)
  - [Subscribe to row for all column changes](#subscribe-to-row-for-all-column-changes)
  - [Subscribe to multiple resources in a single request](#subscribe-to-multiple-resources-in-a-single-request)
  - [Subscribe to multiple resources in multiple requests](#subscribe-to-multiple-resources-in-multiple-requests)
  - [Subscribe to table and a row is added](#subscribe-to-table-and-a-row-is-added)
  - [Subscribe to table and a row is deleted](#subscribe-to-table-and-a-row-is-deleted)
  - [Subscribe to table and a row is updated](#subscribe-to-table-and-a-row-is-updated)
  - [Subscribe to an invalid column](#subscribe-to-an-invalid-column)
  - [Subscribe to an invalid table](#subscribe-to-an-invalid-table)
  - [Subscribe to an invalid row](#subscribe-to-an-invalid-row)

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
    +-------------------+                           +--------------------+
    |                   |                           |       Ubuntu       |
    |    OpenSwitch     |eth0+-----------------+eth1|                    |
    |                   |         link01            |     Workstation    |
    |                   |                           |                    |
    +-------------------+                           +--------------------+
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


# REST WebSocket Events
##  Subscribe to row for specific column changes
### Objective
The test case verifies that event notifications are received for a subscribed row when specific columns change.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific row and column for notification of changes. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to the `trunks` column of `Port1` row:
    ```
    {
       "subscriptions":[
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1",
             "type":"row",
             "fields":[
                "trunks"
             ]
          }
       ]
    }
    ```

4. Verify that the request was successful by confirming that the response `status` is `successful`.
5. Trigger a notification from the switch by changing the `trunks` column for the row `Port1`. The row is updated by sending a `PUT` request to the path `/rest/v1/system/ports/Port1` with the data in step 2 with `trunks` set to `[400]`.
6. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `2` and `fields` contains the modified `trunks` column. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"2",
             "details":[
                "trunks"
             ],
             "change":"updated"
          }
       ]
    }
    ```

7. Clean up the test data created for the row subscription by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received with the `event_id` equal to `2` and `fields` contains the modified column `trunks`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for `Port1` when the `trunks` column is modified. The test is also considered failing if a notification is received, but `trunks` is not included in the value of `fields`.


##  Subscribe to row for all column changes
### Objective
The test case verifies that event notifications are received for a subscribed row when any columns change.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific row and all columns for notification of changes. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to all column changes for `Port1` row:
    ```
    {
       "subscriptions":[
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1",
             "type":"row",
             "fields":[]
          }
       ]
    }
    ```

4. Verify that the request was successful by confirming that the response `status` is `successful`.
5. Trigger a notification from the switch by changing the `trunks` column for the row `Port1`. The row is updated by sending a `PUT` request to the path `/rest/v1/system/ports/Port1` with the data in step 2 with `trunks` set to `[400]`.
6. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `2` and `fields` contains the modified `trunks` column. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"2",
             "details":[
                "trunks"
             ],
             "change":"updated"
          }
       ]
    }
    ```

7. Clean up the test data created for the row subscription by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received with the `event_id` equal to `2` and `fields` contains the modified column `trunks`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for `Port1` when the `trunks` column is modified.


##  Subscribe to multiple resources in a single request
### Objective
The test case verifies that event notifications are received when subscribing for multiple events in a single request. The test case verifies multiple subscriptions for a table and row.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific row and table for notification of changes in a single request. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to `Port` table and `Port1` row changes:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"Port",
             "type":"table"
          },
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1",
             "type":"row",
             "fields":[
                "trunks"
             ]
          }
       ]
    }
    ```

4. Verify that the request was successful by confirming that the response `status` is `successful`.
5. Trigger a notification from the switch by changing the `trunks` column for the row `Port1`. The row is updated by sending a `PUT` request to the path `/rest/v1/system/ports/Port1` with the data in step 2 with `trunks` set to `[400]`. The update will trigger a notification for both events `1` and `2`.
6. Wait for the event notification and verify that the message includes a notification for `event-id`  `1` and `2`, and `fields` contains the modified `trunks` column. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          },
          {
             "event_id":"2",
             "details":[
                "trunks"
             ],
             "change":"updated"
          }
       ]
    }
    ```

7. Clean up the test data created by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received for events `1` and `2`,  and `fields` contains the modified column `trunks`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for `Port1` row or `Port` table when the `trunks` column is modified.



##  Subscribe to multiple resources in multiple requests
### Objective
The test case verifies that event notifications are received when subscribing for multiple events in multiple requests. The test case verifies multiple subscriptions for a table and row.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific row and table for notification of changes in multiple requests. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to the `Port` table:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"Port",
             "type":"table"
          }
       ]
    }
    ```

4. Verify that the request was successful by confirming that the response `status` is `successful`.
5. Send an event subscription request to the switch with the following data to subscribe to the `Port1`  row:
    ```
    {
       "subscriptions":[
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1",
             "type":"row",
             "fields":[
                "trunks"
             ]
          }
       ]
    }
    ```

6. Verify that the request was successful by confirming that the response `status` is `successful`.
7. Trigger a notification from the switch by changing the `trunks` column for the row `Port1`. The row is updated by sending a `PUT` request to the path `/rest/v1/system/ports/Port1` with the data in step 2 with `trunks` set to `[400]`. The update will trigger a notification for both events `1` and `2`.
8. Wait for the event notification and verify that the message includes a notification for `event-id`  `1` and `2`, and `fields` contains the modified `trunks` column. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          },
          {
             "event_id":"2",
             "details":[
                "trunks"
             ],
             "change":"updated"
          }
       ]
    }
    ```

9. Clean up the test data created by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received for events `1` and `2`,  and `fields` contains the modified column `trunks`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for `Port1` row or `Port` table when the `trunks` column is modified.



##  Subscribe to table and a row is added
### Objective
The test case verifies that event notifications are received for a subscribed table when a row is added.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific table for notification of changes. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Send an event subscription request to the switch with the following data to subscribe to the table `Port` for changes:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"Port",
             "type":"table"
          }
       ]
    }
    ```

3. Verify that the request was successful by confirming that the response `status` is `successful`.
4. Trigger a notification by adding a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

5. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `1`. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          }
       ]
    }
    ```

6. Clean up the test data created by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received with the `event_id` equal to `1`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for the `Port` table when a new row is added.



##  Subscribe to table and a row is deleted
### Objective
The test case verifies that event notifications are received for a subscribed table when a row is deleted.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific table for notification of changes. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to the table `Port` for changes:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"Port",
             "type":"table"
          }
       ]
    }
    ```

4. Verify that the request was successful by confirming that the response `status` is `successful`.
5. Trigger a notification by deleting the row `Port1` by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.
6. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `1`. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          }
       ]
    }
    ```

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received with the `event_id` equal to `1`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for the `Port` table when a row is deleted.



##  Subscribe to table and a row is updated
### Objective
The test case verifies that event notifications are received for a subscribed table when a row is updated.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to a specific table for notification of changes. The test case validates the message constructs and the notification data against the requested subscriptions.

1. Establish a websocket connection to the switch at path `/ws`.
2. Send an event subscription request to the switch with the following data to subscribe to the table `Port` for changes:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"Port",
             "type":"table"
          }
       ]
    }
    ```

3. Verify that the request was successful by confirming that the response `status` is `successful`.
4. Trigger a notification by adding a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

5. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `1`. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          }
       ]
    }
    ```

6. Trigger a notification from the switch by changing the `trunks` column for the row `Port1`. The row is updated by sending a `PUT` request to the path `/rest/v1/system/ports/Port1` with the data in step 4 with `trunks` set to `[400]`.
7. Wait for the event notification and verify that the message includes a notification for `event-id` with the value `1`. The notification should include:
    ```
    {
       "notifications":[
          {
             "event_id":"1",
             "change":"updated"
          }
       ]
    }
    ```

8. Clean up the test data created by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a notification message is received with the `event_id` equal to `1`.

#### Test fail criteria
The test is considered failing if the subscription request results in an `unsuccessful` response or if a notification request is not received for the `Port` table when a row is updated.



##  Subscribe to an invalid column
### Objective
The test case verifies that the event subscription request fails when subscribing to an invalid column.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and attempts to subscribe to a specific row and column for notification of changes. The test case validates the error response from the switch when subscribing to an invalid column.

1. Establish a websocket connection to the switch at path `/ws`.
2. Add a new entry in the Port table by sending a `POST` request to path `/rest/v1/system/ports`, used for subscribing, with the following data:
    ```
    {
        "configuration": {
            "name": "Port1",
            "interfaces": ["/rest/v1/system/interfaces/1"],
            "trunks": [413],
            "ip4_address_secondary": ["192.168.1.1"],
            "lacp": "active",
            "bond_mode": "l2-src-dst-hash",
            "tag": 654,
            "vlan_mode": "trunk",
            "ip6_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "external_ids": {"extid1key": "extid1value"},
            "mac": "01:23:45:67:89:ab",
            "other_config": {"cfg-1key": "cfg1val"},
            "bond_active_slave": "null",
            "ip6_address_secondary": ["01:23:45:67:89:ab"],
            "ip4_address": "192.168.0.1",
            "admin": "up",
            "ospf_auth_text_key": "null",
            "ospf_auth_type": "null",
            "ospf_if_out_cost": 10,
            "ospf_if_type": "ospf_iftype_broadcast",
            "ospf_intervals": {"transmit_delay": 1},
            "ospf_mtu_ignore": False,
            "ospf_priority": 0,
        },
        "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
    }
    ```

3. Send an event subscription request to the switch with the following data to subscribe to an invalid column for `Port1` row:
    ```
    {
       "subscriptions":[
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1",
             "type":"row",
             "fields":["invalid_column"]
          }
       ]
    }
    ```

4. Verify that the request was unsuccessful by confirming that the response `status` is `unsuccessful` and that the response includes `invalid_column` in the `messages` field. The response should look like the following:
    ```
    {
       "status":"unsuccessful",
       "errors":[
          {
             "event_id":"2",
             "messages":[
                "Invalid column invalid_column"
             ]
          }
       ]
    }
    ```

5. Clean up the test data created by sending a `DELETE` request to path `/rest/v1/system/ports/Port1` and verify the response status is `204`.

### Test result criteria
#### Test pass criteria
The test case is considered passing if a response is received with the `status` equal to `unsuccessful` and `messages` contains the `invalid_column` error.

#### Test fail criteria
The test is considered failing if the subscription request results in a `successful` response or if the `invalid_column` error is not present in the `messages` field.



##  Subscribe to an invalid table
### Objective
The test case verifies that the event subscriptions request fail when subscribing to an invalid column.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and subscribes to an invalid table to validate the error response from the switch.

1. Establish a websocket connection to the switch at path `/ws`.
2. Send an event subscription request to the switch with the following data to subscribe to an invalid table:
    ```
    {
       "subscriptions":[
          {
             "event_id":"1",
             "resource":"InvalidTable",
             "type":"table",
          }
       ]
    }
    ```

3. Verify that the request was unsuccessful by confirming that the response `status` is `unsuccessful` and that the response includes `InvalidTable` in the `messages` field. The response should look like the following:
    ```
    {
       "status":"unsuccessful",
       "errors":[
          {
             "event_id":"1",
             "messages":[
                "Invalid table name InvalidTable"
             ]
          }
       ]
    }
    ```

### Test result criteria
#### Test pass criteria
The test case is considered passing if a response is received with the `status` equal to `unsuccessful` and `messages` contains the `InvalidTable` error.

#### Test fail criteria
The test is considered failing if the subscription request results in a `successful` response or if the `InvalidTable` error is not present in the `messages` field.



##  Subscribe to an invalid row
### Objective
The test case verifies that the event subscription request fails when subscribing to an invalid row.

### Requirements
Physical or virtual switches are required for this test.

### Setup
#### Topology diagram

```ditaa
    +----------------+         +----------------+
    |                |         |                |
    |                |         |                |
    |   Local Host   +---------+     Switch     |
    |                |         |                |
    |                |         |                |
    +----------------+         +----------------+
```

#### Test Setup
The local host is connected to the switch using websockets.

### Description
The test case establishes a websocket connection with the switch and attempts to subscribe to a specific row and column for notification of changes. The test case validates the error response from the switch when subscribing to an invalid row.

1. Establish a websocket connection to the switch at path `/ws`.
2. Send an event subscription request to the switch with the following data to subscribe to an invalid row:
    ```
    {
       "subscriptions":[
          {
             "event_id":"2",
             "resource":"/rest/v1/system/ports/Port1Invalid",
             "type":"row",
             "fields":[]
          }
       ]
    }
    ```

3. Verify that the request was unsuccessful by confirming that the response `status` is `unsuccessful` and that the response includes `Port1Invalid` in the `messages` field. The response should look like the following:
    ```
    {
       "status":"unsuccessful",
       "errors":[
          {
             "event_id":"2",
             "messages":[
                "Invalid resource URI /rest/v1/system/ports/Port1Invalid"
             ]
          }
       ]
    }
    ```

### Test result criteria
#### Test pass criteria
The test case is considered passing if a response is received with the `status` equal to `unsuccessful` and `messages` contains the `Port1Invalid` error.

#### Test fail criteria
The test is considered failing if the subscription request results in a `successful` response or if the `Port1Invalid` error is not present in the `messages` field.
