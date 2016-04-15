# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

from opsrest.manager import OvsdbConnectionManager
from tornado.log import app_log


class OvsdbNotificationMonitor:
    def __init__(self, remote, schema, notification_callback):
        self.remote = remote
        self.schema = schema
        self.tables_monitored = set([])
        self.manager = None
        self.notify_cb = notification_callback

    def add_table_monitor(self, table):
        app_log.debug("Adding monitoring for table %s" % table)

        if table not in self.tables_monitored:
            self.tables_monitored.add(table)
            self.restart_monitoring()

    def remove_table_monitor(self, table):
        app_log.debug("Removing monitoring for table %s" % table)

        if table in self.tables_monitored:
            self.tables_monitored.discard(table)
            self.restart_monitoring()

    def restart_monitoring(self):
        app_log.debug("Restarting monitor..")

        new_manager = self.start_new_manager()

        if self.manager:
            # Check if there are any pending changes and notify before stopping
            self.manager.idl_check_and_update()
            self.manager.stop()

        self.manager = new_manager

        # Track all columns of all tables that are registered/monitored
        self.manager.idl.track_add_all()

    def start_new_manager(self):
        app_log.debug("Starting new manager")

        manager = OvsdbConnectionManager(self.remote, self.schema)
        manager.start(self.tables_monitored)
        manager.add_change_callback(self.notify_cb)

        return manager
