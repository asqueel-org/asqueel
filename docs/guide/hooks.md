# Add business behavior to a table

A table can select a `SqlTable` subclass with `x_table_class`. The native hook
profile supports insertion, update and deletion:

```python
from asqueel import SqlDatabaseConfig, SqlTable


class CustomerTable(SqlTable):
    def trigger_onInserting(self, record):
        record["name"] = record["name"].strip()
        if not record["name"]:
            raise ValueError("Customer name is required")

    def trigger_onInserted(self, record):
        # On PostgreSQL, values the database decided are already in the record.
        pass


class ShopWithBehavior(SqlDatabaseConfig):
    def main(self, root):
        customer = root.db("shop", implementation="postgres", conninfo="dbname=shop").schemas().schema(
            "sales",
        ).tables().table("customer", pkey="id", x_table_class=CustomerTable)
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T")
```

The hooks receive the caller's record itself, not a copy: a change made by
`trigger_onInserting` is what the INSERT writes, and the caller sees it after
the call. On PostgreSQL, values the database decides are written into the record
before `trigger_onInserted`. Hooks may use other tables on the same database;
those operations join the same connection. A Python error inside the cycle makes
the connection rollback-only, including an error before any SQL. Hooks cannot
commit or roll back during a write.

For updates, override `trigger_onUpdating(record, old_record=None)` and/or
`trigger_onUpdated(record, old_record=None)`. For physical deletion, override
`trigger_onDeleting(record)` and/or `trigger_onDeleted(record)`.

For an ordinary table, `old_record` is what the caller passed to `update()`.
Tables with hierarchy, protected/generated columns or an active write partition
reread the stored row with a lock before validation and hooks. Hierarchical
updates still require the caller to supply `old_record`; the reread prevents a
stale snapshot from bypassing cycle checks. For other tables, read it yourself
with `query(where=..., for_update=True).fetchRecord()` when hooks need it. `delete()` with a
key string, or with a record lacking physical columns, reads the row with a lock
before the hooks.

To refuse a write, override `protect_update(record, old_record=None)`,
`protect_delete(record)` or `protect_validate(record, old_record=None)` and
raise `self.exception('protect_update', record=record, msg=...)` (or
`'protect_delete'`, `'protect_validate'`).

Column triggers run in the same cycle: a column attribute `onInserting`,
`onUpdating`, `onDeleting`, `onInserted`, `onUpdated` or `onDeleted` names a
method `trigger_<name>` of the table (or of `trigger_table`), called with the
record and `fldname`; a callable is called with the record and the column name.

Draft and logical-deletion read filters do not hide the row being written, and
active physical partitions constrain writes before hooks. Related SQL writes share the rollback;
external side effects, such as sending messages, cannot be undone by it.

The full order of each cycle is in [writes](writes.md).


## Follow the write's parent

Inside a table hook, `self.currentTrigger` (also `self.db.currentTrigger`)
describes the current application write: `event`, logical `table`, `record`,
`old_record`, `parent` and zero-based `level`. A write issued inside another
write's hook has that operation as its parent. Top-level writes have level 0
and no parent. On return, the caller's context is restored; after the outermost
write, `currentTrigger` is None. Cleanup also runs when a hook raises.

This is a causal stack for synchronous application writes. It is separate from
the independent transaction queues selected by connection name, and it does not
represent native database triggers. Deferred work executes at commit time, after
the originating write has left the stack. Pass needed identifiers to the callback
rather than relying on `currentTrigger` to retain the old write.

Hooks can register `deferToCommit`, `deferAfterCommit` and `deferredRaise`.
Use the [commit lifecycle](transactions.md#deferred-work) to choose the
correct boundary and understand callback ordering and failure handling.

## Choose the right layer for a rule

Use a before-hook to normalize or validate the outgoing record. Use an after-hook
for additional SQL work that must succeed or fail in the same transaction. The
name “after” means after the statement, **not after commit**. Use
`deferToCommit()` for work before the database commit and `deferAfterCommit()`
for work that follows a successful commit. A post-commit callback does not by
itself guarantee reliable external delivery; that requires an application-level
persistence and retry strategy.

A subclass configured on one table affects that table's application operations.
Raw `CompiledQuery` execution and independently constructed low-level compilers
do not invoke these table hooks. Database constraints remain the appropriate
place for invariants that every SQL client must enforce.

Native database triggers execute in the database and are described with its
structural objects for schema management. Python hooks execute in the application.
Use both when their responsibilities differ, and avoid duplicating a business
action in both mechanisms.

## Lifecycle at a glance

| Operation | Before SQL | After SQL, before commit |
|---|---|---|
| Insert | `trigger_onInserting(record)` | `trigger_onInserted(record)` |
| Update | `trigger_onUpdating(record, old_record=None)` | `trigger_onUpdated(record, old_record=None)` |
| Physical delete | `trigger_onDeleting(record)` | `trigger_onDeleted(record)` |

`sql_insert`, `sql_update` and `sql_delete`, and `query(...).sql_update()` /
`.sql_delete()`, run no hooks. `query(...).update()` and `.delete()` run them
for each selected row.

See [writes](writes.md) for selectors and returned values, and
[transactions](transactions.md) for failure recovery.

## Database-level write cycle

Table commands delegate to `db.insert(table, record)`, `db.update(table, record,
old_record=None, pkey=None)` and `db.delete(table, record)`, which run the cycle
with the table's hooks. There are no shared database-level hooks: no
`onWriting`, `onWritten` or `_onDbChange`. Change log, totalizers and package triggers
are not executed; their mapping is tracked in
[Adattamenti legacy](../adattamenti-legacy.md).


## Standalone table behaviors

`auto_counter` assigns MAX + 1 when its field is omitted or None. Its scope
can contain one or several physical columns, including NULL values. Explicit
positions are preserved. Deleted maximum positions may be reused.
`relative_index` instead increments a persistent counter in the master's
`_xtd` table: deletion does not rewind it, but transaction rollback does.
The extension needs `main_id` and an `id` or `main_id` primary key.

`hierarchical` maintains paths, root IDs and inherited fields through inserts,
renames, moves and cascades. Custom parent/counter columns and `linked_to`
master roots are supported. A moved node takes the last sibling position;
the existing 1295-sibling bound remains. Keys cannot change or contain `/`.
Before-hooks may normalize source fields: paths are recomputed before SQL.
`depth` remains explicitly unsupported at model construction.

Hierarchy and counter operations take a PostgreSQL `SHARE ROW EXCLUSIVE`
table lock before reading rows; SQLite takes its write reservation. Locks last
until commit/rollback. Use short transactions; callers own deadlock retries.
Concurrency tests use PostgreSQL's default READ COMMITTED isolation.

A column's `default` fills omitted values, leaving explicit None unchanged.
`read_only` rejects caller assignments on insert (except a `sys_fields` ID)
and changes on update. `unmodifiable` allows insert and rejects later changes.
Database-generated columns are omitted from ordinary UPDATE assignments;
changing their value or explicitly assigning them through SQL APIs raises.

`sql_insert`, `sql_update` and `sql_delete` bypass Python defaults, column
protections and hierarchy/counter maintenance. They still enforce active
physical partitions unless `ignore_partition=True` is explicit. Structural
cascades and descendant maintenance include rows hidden by read filters and
partitions, so an entire tree remains consistent within the transaction.
