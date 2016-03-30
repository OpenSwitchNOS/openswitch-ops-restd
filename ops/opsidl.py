from ovs.db.idl import Idl, Row
import ovs

ROW_CREATE = "create"
ROW_UPDATE = "update"
ROW_DELETE = "delete"


class OpsIdl(Idl):
    """
    OpsIdl inherits from Class Idl. The index to row mapping feature
    is used in order to improve dc write time by doing the lookup from
    the index_map.

    """
    def __init__(self, remote, schema):
        Idl.__init__(self, remote, schema)
        for table in self.tables.itervalues():
            table.index_map = {}

    def _Idl__clear(self):
        changed = False

        for table in self.tables.itervalues():
            if table.rows:
                changed = True
                table.rows = {}
                table.index_map = {}

        if changed:
            self.change_seqno += 1

    # Overriding parent process_update
    def _Idl__process_update(self, table, uuid, old, new):
        """Returns True if a column changed, False otherwise."""
        row = table.rows.get(uuid)
        changed = False
        if not new:
            # Delete row.
            if row:
                self._update_index_map(row, table, ROW_DELETE)
                del table.rows[uuid]
                changed = True
                self.notify(ROW_DELETE, row)
            else:
                # XXX rate-limit
                vlog.warn("cannot delete missing row %s from table %s"
                          % (uuid, table.name))
        elif not old:
            # Insert row.
            if not row:
                row = self._Idl__create_row(table, uuid)
                changed = True
            else:
                # XXX rate-limit
                vlog.warn("cannot add existing row %s to table %s"
                          % (uuid, table.name))
            if self._Idl__row_update(table, row, new):
                changed = True
                self.notify(ROW_CREATE, row)

            self._update_index_map(uuid, table, ROW_CREATE)
        else:
            op = ROW_UPDATE
            if not row:
                row = self._Idl__create_row(table, uuid)
                changed = True
                op = ROW_CREATE
                # XXX rate-limit
                vlog.warn("cannot modify missing row %s in table %s"
                          % (uuid, table.name))
            if self._Idl__row_update(table, row, new):
                changed = True
                self.notify(op, row, Row.from_json(self, table, uuid, old))

            if op == ROW_CREATE:
                self._update_index_map(uuid, table, ROW_CREATE)

        return changed

    def _update_index_map(self, uuid, table, operation):

        if operation == ROW_DELETE:
            index = self._row_to_index_lookup(row, table)
            if index in table.index_map:
                del table.index_map[index]

        elif operation == ROW_CREATE:
            if table.indexes:
                row = table.rows[uuid]
                index_values = []
                for v in table.indexes[0]:
                    if v.name in row._data:
                        column = table.columns.get(v.name)
                        if column.type.key.type == ovs.db.types.UuidType:
                            val = new[v.name][1]
                        else:
                            val = row.__getattr__(v.name)
                        val = str(val)
                        index_values.append(val)
                table.index_map[tuple(index_values)] = table.rows[uuid]

    def index_to_row_lookup(self, index, table_name):
        """
        This subroutine fetches the row reference using index_values.
        index_values is a list which contains the combination indices
        that are used to identify a resource.
        """
        table = self.tables.get(table_name)
        index = tuple([str(item) for item in index])
        if index in table.index_map:
            return table.index_map[index]

        return None

    def _row_to_index_lookup(self, row, table):
        # Given the row return the index
        index_values = []
        if not table.indexes:
            return None
        for v in table.indexes[0]:
            val = row.__getattr__(v.name)
            if isinstance(val, Row):
                val = val.uuid
            val = str(val)
            index_values.append(val)
        return tuple(index_values)
