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
database; those operations participate in the same connection. A hook failure marks
the unit of work rollback-only, including a failure before any SQL. Hooks cannot
commit, roll back or close the database during a write.

For updates, override `trigger_onUpdating(record, old_record=None)` and/or
`trigger_onUpdated(record, old_record=None)`. For physical deletion, override
`trigger_onDeleting(record)` and/or `trigger_onDeleted(record)`.

Ordinary update and delete always first read and lock the
matching record with PostgreSQL `FOR UPDATE OF` the base table. A declared primary
key and exactly one matching row are required; missing or multiple matches raise
`RecordNotFoundError` or `RecordMultipleRowsError` before any hook runs. Locks last
until commit or rollback. This single-record contract also applies when no hook is overridden.
Use raw commands for predicates affecting multiple rows.

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

Ordinary update/delete locks exactly one existing row before hooks. Adding a
hook does not change cardinality. A broad predicate must use raw update/delete
when per-record Python table triggers are intentionally bypassed.

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

`table.raw_insert`, `raw_update` and `raw_delete` also exist on `db`, with the
table as first argument. They bypass Python table triggers, not DB hooks,
policies, parameterization, SQL triggers or transaction/error handling.

- Raw insert accepts a mapping or a list of mappings. Shared hooks run once per
  inserted record, in list order, and receive that record. Returned physical
  values are available to after-hooks. No intermediate commit occurs.
- Raw update executes one SQL statement for its entire predicate. Shared hooks
  run once, receiving only the supplied update values, without an old snapshot.
  Before-hooks may modify those values before SQL compilation.
- Raw delete executes one SQL statement. For a key/record selector, shared hooks
  receive a copied key mapping or the supplied record. For an explicit predicate
  they receive `record=None`. This is selector information, not a loaded row;
  mutating it does not change the compiled deletion predicate.

Overriding shared hooks never turns a raw command into a single-record command.
Raw update/delete call them even when zero rows match, and provide no implicit
per-row events. Hook implementations must branch on `raw`/`_raw` and tolerate
partial records or `None`. For raw commands `old_record` remains `None`.

The native shared hooks do not implement Genropy field/package dispatch,
counters, totalizers or notifications. Their mapping is tracked in
[Adattamenti legacy](../adattamenti-legacy.md).
