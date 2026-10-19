# Insert, update and delete records

`insert`, `update` and `delete` run the GenroPy write cycle: table triggers,
column triggers, `protect_*` checks and the actions on related records, in the
legacy order. `insert` and `update` modify the caller's record in place and
return it. Every command joins the pending transaction of the selected
connection; none commits. Use `db.commit()` / `db.rollback()` for each unit of
work. Examples below use the [tutorial model](tutorial.md) and are independent
operations, not another seed script.

A table that declares something the cycle does not execute yet (for example
`sys_fields`, or a column `default`) is refused with `UnsupportedFeatureError`
before any trigger or SQL. The list, with its issues, is in
[current status](limitations.md#what-the-write-cycle-refuses).

## Insert a record

```python
try:
    customer = db.table("sales.customer")
    record = customer.insert({"id": 3, "name": "Katherine"})
    db.commit()
except Exception:
    db.rollback()
    raise

```

Mapping keys are logical column names without `$`. Values are data, not SQL
expressions. Only physical columns become SQL columns: alias, formula and
`@path` keys, and unknown names, are ignored without error. Columns whose value
is `None` are left out of the INSERT, so database defaults apply.

The cycle runs in this order: key assignment, `protect_validate`, column
`onInserting` triggers, `trigger_onInserting`, `trigger_assignCounters`,
`protect_draft`, the INSERT, column `onInserted` triggers, `trigger_onInserted`.
See [hooks](hooks.md) for the methods a table subclass can override.

A key that is `None` or `''` is generated before the triggers: `max(key)+1`
for an integer key, a 22-character UUID for a text key with size 22 or no size,
or the value of the
table's `newPkeyValue()` when it is overridden. `max(key)+1` is not safe under
concurrent inserts; use a `serial` column or your own `newPkeyValue()` there.

On PostgreSQL, the INSERT reads back with RETURNING the columns whose value the
database decides (`sql_value`, generated columns, omitted columns declaring
`sql_default`) and writes them into the record. A database default the model does
not declare is applied but not read back: read the row again to see it. SQLite has no RETURNING in the write
cycle. There is no `returning=` argument.

## Update a record

```python
try:
    customer = db.table("sales.customer")
    old_record = dict(customer.query(where="$id = :id", id=3, for_update=True).fetchRecord())
    record = dict(old_record, name="Katherine Johnson")
    customer.update(record, old_record)
    db.commit()
except Exception:
    db.rollback()
    raise

```

`update(record, old_record=None, pkey=None)` takes the key of the row to change
from `old_record`, then from `pkey`, then from the record itself. To change a
key, pass the old row as `old_record` and the new key in the record.
`old_record` is never read from the database: read it yourself, with
`for_update=True` when the row must stay locked until commit.

Every physical column present in the record is written, `None` included. Pass
the complete row, as above, or only the columns to change with their key:
`customer.update({"id": 3, "name": "Katherine Johnson"})`. Without `old_record`
the update raises `ValueError` when a relation pointing to this table declares
`onUpdate`: the cycle needs the old key to apply it. The UPDATE does not check
how many rows it changed.

`insertOrUpdate(record)` reads the row of the record's key with
`for_update=True` and the query's default filters. Without a row it runs
`insert(record)`; with a row it runs `update(record, old_record=<that row>)`.
It returns the record in both cases.

The cycle runs `protect_update`, `protect_validate`, column `onUpdating`
triggers, `trigger_onUpdating`, `protect_draft`, `trigger_assignCounters`, the
UPDATE, then the `onUpdate` actions of the relations pointing to this table when
its key changed, column `onUpdated` triggers and `trigger_onUpdated`.

## Delete a record

```python
try:
    db.table("sales.line").delete({"id": 101})
    db.commit()
except Exception:
    db.rollback()
    raise

```

`delete()` accepts a key string or a record. A key string is read again, with a
lock, and its row enters the cycle; a missing key string returns without error.
A record is deleted as given, without reading it again. The DELETE must remove exactly one row, otherwise it
raises `RecordNotFoundError`. A table declared with `deletable=False` refuses
every delete.

Before the DELETE, the cycle applies the `onDelete` action of each relation
pointing to this table: `raise` refuses the delete while related rows exist,
`cascade` deletes them through their own cycle, `setnull` clears their foreign
key through an update, `ignore` (the default) does nothing.

`delete()` is always a physical DELETE, also on a table with a logical-deletion
policy. To mark a row as deleted, write its logical-deletion column with
`update()`.

## Write without triggers

The `sql_*` commands write the statement directly, without triggers,
`protect_*` checks or related-record actions:

```python
try:
    customer = db.table("sales.customer")
    customer.sql_insert([
        {"id": 11, "name": "Grace"},
        {"id": 12, "name": "Alan"},
    ])
    customer.sql_update({"id": 11, "name": "Grace Hopper"})
    customer.sql_delete({"id": 12})
    db.commit()
except Exception:
    db.rollback()
    raise

```

- `sql_insert(record)` accepts one record or a list. A missing key is
  assigned first, as `checkPkey` does; in a list each further integer key is
  the next integer. A key the database generates (`serial`, `sql_default`) is
  not assigned. A list runs one `executemany` per group of consecutive records
  with the same columns, without RETURNING.
- `sql_update(record, old_record=None, pkey=None)` takes the key like `update`.
- `sql_delete(record)` deletes by the record's key and does not check the row count.

A query can write the rows it selects. Its filters, order and limit decide the
rows; the result is the affected row count:

```python
try:
    changed = db.table("sales.invoice").query(
        where="$total >= :minimum", minimum=100,
    ).sql_update({"note": "Reviewed"})
    db.commit()
except Exception:
    db.rollback()
    raise

```

`query(...).sql_delete()` deletes the selected rows in the same way. A query
with `group_by` or `having` is refused. The query's parameter names and the
value names must differ.

## Composite keys

A table whose `pkey` is a compositeColumn identifies a row by the serialized
key: the JSON list of the members, with dates, timestamps, times and decimals
as typed text (`'["a", "2026-01-01::D"]'`). `insert` assigns it to the
compositeColumn of the record when it is None or ''. It is the same string the
compositeColumn returns when read. `update(record, pkey=...)` and
`delete(...)` take it as a string; a tuple or mapping raises `ValueError`.

## Bag values

A `genro_bag.Bag` written to a column becomes its XML (`to_xml()`); an empty
Bag becomes NULL. A read returns the XML string; `#BAG` in the query columns
turns it back into a Bag.

## Lock a table

`table.lock(mode='ACCESS EXCLUSIVE', nowait=False)` locks the table in the
current transaction. On PostgreSQL it runs `LOCK <table> IN <mode> MODE`, with
`NOWAIT` when asked; `mode` is one of the PostgreSQL lock modes, another value
raises `ValueError`. On SQLite it takes the write reservation, as a
`for_update` query does. The lock ends at commit or rollback.

## Understand the write boundary

- Partitions filter reads only. `insert` does not fill the partition column and
  `update`/`delete` do not check the row's partition, as in GenroPy
  ([#15](https://github.com/asqueel-org/asqueel/issues/15)).
- Draft and logical-deletion read filters do not restrict writes.
- An SQL execution error rolls back the pending transaction of the selected
  connection. A Python error inside the cycle makes the connection
  rollback-only: call `db.rollback()` before reusing it.
- Do not read zero affected rows as an access error, and do not retry an
  unknown commit outcome silently.

Next: [transactions](transactions.md), [business hooks](hooks.md), and
[troubleshooting](troubleshooting.md).
