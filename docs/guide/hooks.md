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
        # Returned fields, when requested, are available in this record.
        pass


class ShopWithBehavior(SqlDatabaseConfig):
    def main(self, root):
        customer = root.db("shop", conninfo="dbname=shop").schemas().schema(
            "sales",
        ).tables().table("customer", pkey="id", x_table_class=CustomerTable)
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T")
```

The input mapping is copied before the before-insert hook. Returned fields are
overlaid before the after-insert hook. Hooks may use other tables on the same
database; those operations participate in the same session. A hook failure marks
the unit of work rollback-only, including a failure before any SQL. Hooks cannot
commit, roll back or close the database during a write.

For updates, override `trigger_onUpdating(record, old_record=None)` and/or
`trigger_onUpdated(record, old_record=None)`. For physical deletion, override
`trigger_onDeleting(record)` and/or `trigger_onDeleted(record)`.

When an update or delete hook is overridden, the table first reads and locks the
matching record with PostgreSQL `FOR UPDATE OF` the base table. A declared primary
key and exactly one matching row are required; missing or multiple matches raise
`RecordNotFoundError` or `RecordMultipleRowsError` before any hook runs. Locks last
until commit or rollback. Without overridden hooks, explicit predicates retain
the existing set-based update/delete behavior.

The update before-hook receives the complete physical row overlaid with the
caller's changes. It may modify that record. Both update hooks receive independent
copies of the original locked row as `old_record`. SQL targets the saved old key,
so changing a key in the new record does not redirect the update. Delete hooks
share the loaded record, but changing its key cannot redirect deletion either.
Returned physical fields are mapped back by column identity before the update
after-hook; returning aliases do not rename record fields.

Draft and logical-deletion read filters do not hide the row being written;
partition restrictions still apply. `soft_delete()` and `restore()` follow the
update hook lifecycle. An unexpected affected-row count makes the unit of work
rollback-only, as does any hook error. Related SQL writes share this rollback;
external side effects, such as sending messages, cannot be undone by it.

Application integration connects package contributions, field-level behavior,
protection rules and related-record operations to the write lifecycle. Keep the
execution order explicit: validation, SQL work and post-commit effects belong
to different stages.


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
| Soft-delete / restore | The update lifecycle | The update lifecycle |

Hooked update/delete reads lock exactly one existing row first. This changes the
semantics of a broad predicate: adding a hook to an existing table can turn a
previously valid multirow operation into an explicit multiple-record error.
Review callers when introducing those hooks.

See [writes](writes.md) for selectors and returned values, and
[transactions](transactions.md) for failure recovery.

## Database-level write lifecycle and raw commands

Table commands delegate to `db.insert(table, values)`, `db.update(table, ...)`
and `db.delete(table, ...)`. The DB accepts a table handle belonging to it or a
logical table name. Its cycle is:

1. `onWriting(table, event, record, old_record=None, raw=False)`.
2. The table's before-hook, unless raw.
3. `onExecutingWrite(...)`, immediately before compilation/execution of the write.
4. `db.execute(...)`, followed by mapping RETURNING values to the record.
5. `_onDbChange(table, event, record, old_record=None, _raw=False)`.
6. The table's after-hook, unless raw.
7. `onWritten(...)`, after the write cycle and still before commit.

Override the shared hooks on an `AsqueelDb` subclass. Events are `I`, `U` and
`D`; the raw flag is a keyword argument. The `_raw` spelling on `_onDbChange`
follows the legacy extension point. Default shared hooks do nothing. They can
perform nested writes or defer callbacks, but cannot commit/rollback inside a
write. Any Python failure makes the selected connection rollback-only.

`table.raw_insert`, `raw_update` and `raw_delete` have the corresponding ordinary
method signatures and also exist on `db`, with the table as first argument.
They bypass table triggers, not DB hooks, policies, parameterization or change
tracking. Overriding a shared hook makes update/delete use a locked single record
so the hook receives complete data; a predicate selecting zero or multiple rows
fails before the hook. Without shared/table hooks, predicate writes may affect
multiple rows.

The native shared hooks do not implement Genropy field/package dispatch,
counters, totalizers or notifications. Their mapping is tracked in
[Adattamenti legacy](../adattamenti-legacy.md).
