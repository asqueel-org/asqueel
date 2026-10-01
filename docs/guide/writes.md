# Insert, update and delete records

Table writes execute immediately and return `QueryResult`. They join the
application database's pending transaction; they do not commit independently.
Use `db.commit()` / `db.rollback()` for each unit of work. Examples below use the
[tutorial model](tutorial.md) and are independent operations, not another seed
script to run against the same identifiers.

## Insert a record and read returned values

```python
try:
    result = db.table("sales.customer").insert(
        {"id": 3, "name": "Katherine"}, returning="$id, $name",
    )
    saved = result.rows[0]
    db.commit()
except Exception:
    db.rollback()
    raise

```

Mapping keys are logical column names without `$`. Values are data, not SQL
expressions. Unknown columns, aliases and formulas are rejected in write values.
The mapping is copied before hooks run; editing it after the call does not save
another change.

`returning='*'` is the default and returns **physical columns only**. Unlike
SELECT `*`, it excludes virtual columns. Use `returning=None` when returned rows
are unnecessary. A simple SQL formula can be explicitly requested, but a
relation-dependent or structured subquery formula requires a separate SELECT.

Database constraints and server defaults still apply. An empty insert mapping
requests DEFAULT VALUES, with any required partition values filled first. Genro
SQL does not automatically generate keys from a `pkey` declaration; define and
manage the database's generation strategy explicitly if keys are not supplied.

## Update by primary key

```python
try:
    result = db.table("sales.customer").update(
        {"id": 3, "name": "Katherine Johnson"}, returning="$id, $name",
    )
    db.commit()
except Exception:
    db.rollback()
    raise

```

Without `where`, the mapping must contain the complete declared primary key.
For composite keys, supply every component. Zero is a valid key; `None` is not.
Ordinary update locks one record and merges the supplied values into its
complete physical row before running the write lifecycle. The before-hook
receives that merged record. This behavior does not depend on overriding hooks.

Do not pass a full SELECT result containing virtual columns back to `update()`.
Choose the writable columns explicitly. UI metadata such as a read-only hint
is display information; it is not write authorization.

## Raw update using a predicate

```python
try:
    result = db.table("sales.invoice").raw_update(
        {"note": "Reviewed"}, where="$total >= :minimum",
        sqlparams={"minimum": 100}, returning="$id, $note",
    )
    db.commit()
except Exception:
    db.rollback()
    raise

```

`raw_update` performs one SQL UPDATE over all matching rows in the partition
scope, without Python table triggers. `result.rowcount` reports affected rows;
zero is a normal outcome. Shared DB hooks run once for the operation, even if
multiple rows match. Database triggers and constraints still apply.

Ordinary `update(..., where=...)` instead requires exactly one matching record:
zero raises `RecordNotFoundError`, multiple matches raise `RecordMultipleRowsError`,
before write hooks run. A declared primary key is required, regardless of hooks.

To change a key, use an explicit predicate selecting the old key and a mapping
containing the new value. Database foreign-key constraints may prevent that
change. Define related-record behavior explicitly through constraints and
application lifecycle rules.

A nonempty selector is required. For raw commands, use `where='TRUE'` only when every row in the
active partition scope is intended. Values are bound data: a value such as
`{'total': '$total + 1'}` is a string, not an increment expression.

## Delete physically

```python
try:
    result = db.table("sales.customer").delete(3, returning="$id")
    db.commit()
except Exception:
    db.rollback()
    raise

```

A complete key mapping or a full record containing the key can also identify
the row. For a predicate, use `delete(where=..., sqlparams=...)`. As with ordinary update,
exactly one row and a declared primary key are required, with or without hooks.
Use `raw_delete(where=..., sqlparams=...)` for a predicate matching zero or more rows;
it bypasses Python table triggers and invokes shared DB hooks once. Foreign keys and database deletion actions still apply.

`delete()` always issues a physical DELETE, including on a table with a logical
deletion policy. It does not switch behavior based on that policy.

## Soft-delete and restore explicitly

For a table declaring `x_logical_deletion_field='deleted_at'`:

```python
from datetime import datetime, timezone

try:
    document = db.table("app.document")
    document.soft_delete(
        value=datetime.now(timezone.utc),
        where="$id=:wanted", sqlparams={"wanted": 100},
    )
    document.restore(where="$id=:wanted", sqlparams={"wanted": 100})
    db.commit()
except Exception:
    db.rollback()
    raise

```

These operations update the marker and follow update hooks. Soft deletion requires
a non-NULL marker; restoration writes NULL. Ordinary SELECT excludes marked
rows by default. See [row policies](row-policies.md) for the model and visibility
options, including how to query deleted rows.

## Raw insertion of one or more records

```python
try:
    customers = db.table("sales.customer")
    customers.raw_insert({"id": 10, "name": "Ada"})
    result = customers.raw_insert([
        {"id": 11, "name": "Grace"},
        {"id": 12, "name": "Alan"},
    ])
    assert result.rowcount == 2
    db.commit()
except Exception:
    db.rollback()
    raise
```

`insert` accepts one mapping and runs Python table triggers. `raw_insert` accepts
one mapping or a list of mappings and skips those triggers. No separate
`insertMany`, `insert_many`, `updateMany` or `deleteMany` method is needed.

A list executes parameterized INSERTs in input order through the common
`db.execute()` path. Records may supply different columns; omitted columns retain
their database defaults. This is not a COPY or executemany optimization. Shared
DB hooks run for each inserted record with the raw flag. Inputs are copied.

The returned `QueryResult` concatenates returned rows and sums rowcount.
`returning=None` returns no rows but keeps the affected count. An empty list is a
no-op returning zero rows/count and empty column metadata, with no write hooks.

The entire list participates in the selected connection's current transaction;
there is no intermediate commit. A SQL error rolls back all pending work,
including earlier writes. A Python hook error requires rollback before reuse.
There is no automatic per-list savepoint or partial-success result.

Raw update/delete do not load per-row snapshots. Shared DB hooks receive the
update values or, for delete-by-key, the supplied record/key mapping. For
predicate deletion they receive `record=None`; `old_record` is always absent
for raw commands. These hooks must not assume a complete record or one event
per affected row. See [the hook contract](hooks.md).

## Understand the write boundary

Partition rules restrict affected rows and validate new partition values. Draft
and logical-deletion **read** filters do not automatically restrict writes. An
ordinary update/deletion reads the physical row with those read filters disabled,
while keeping partition restrictions.

An ordinary SQL execution error automatically rolls back the pending transaction.
A Python write-hook failure instead requires explicit rollback before reuse.
Handle errors around the complete unit of work and use `db.rollback()` for
application-owned recovery. Do not interpret zero affected rows as an access
exception or silently retry an unknown commit outcome.

Next: [transactions](transactions.md), [business hooks](hooks.md), and
[troubleshooting](troubleshooting.md).
