# SQLite

SQLite uses the same `AsqueelDb`, table commands, shared write hooks, raw commands,
`tempEnv`, `execute`, `commit` and `rollback` as PostgreSQL. It uses Python's
standard `sqlite3` driver and requires SQLite 3.35 or later for `RETURNING`.

## Configuration

```python
from asqueel import SqlDatabaseConfig

class Recipe(SqlDatabaseConfig):
    def main(self, root):
        db = root.db()
        db.connection(name='/absolute/path/example.db', implementation='sqlite')
        columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
        columns.column('id', dtype='I')
        columns.column('name', dtype='T')
```

Use an absolute filename for repeatable CLI and Python access. `connection.name`
is the database file; host, port, user and password are not applicable. Optional
`connection.options` supports `timeout` and `cached_statements` from `sqlite3`.

Logical schemas are attached files, matching the existing migration adapter:
`example.db` is the main file and schema `app` uses `example_app.db`. Physical
schema overrides are honored. Attached schema names currently require simple
identifiers; `temp` is reserved. `:memory:` is supported for isolated tests, but
each named/thread connection has a separate in-memory database.

```console
asqueel check --config /path/to/configure.py
asqueel db plan --config /path/to/configure.py
asqueel db apply --config /path/to/configure.py
asqueel shell --config /path/to/configure.py
```

These commands delegate DDL to `asqueel-migration.SqliteDatabase`; Asqueel does
not add another migration engine. CLI migration requires persistent files.
The configured parent directory must exist. Opening a SQLite runtime connection
can create missing files, but it does not create the declared tables.

## Transactions and concurrency

Every SQLite unit of work begins with `BEGIN IMMEDIATE`, including one starting
with a read. This reserves write access before a read/modify/write hook cycle;
`for_update=True` therefore uses connection-level locking, not PostgreSQL row
locks. Other Asqueel connections targeting the same files may block or time out
until explicit completion. Finish a unit of work promptly and do not leave a
read pending while starting another named connection's work.

The underlying semantics are documented by SQLite for
[transactions](https://www.sqlite.org/lang_transaction.html) and
[attached databases](https://sqlite.org/lang_attach.html). This first profile
prioritizes a protected hook cycle over concurrent Asqueel readers. No lock
upgrade, retry or savepoint policy is hidden in the driver.

## Supported scope and differences

The runtime supports parameterized CRUD, `RETURNING`, joins, formulas using
SQLite SQL, pagination, shared write hooks, raw commands, deferred callbacks
and rollback. Raw commands skip table triggers; they retain common DB hooks
and normal compiler/policy checks.

PostgreSQL-specific expressions such as `ILIKE`, `ANY`, array operations and
PostgreSQL casts are not translated into SQLite equivalents. Use expressions
valid for the configured backend. SQLite's native returned types are preserved:
booleans may be integers, dates are ISO strings, and NUMERIC values do not carry
PostgreSQL's decimal precision guarantees. Decimal parameters are passed as
strings for SQLite affinity handling.

The migration adapter's limitations still apply, including unsupported foreign
key DDL and table alterations. SQLite cannot enforce foreign keys across attached
schemas. Logical relationships can still be used for queries; do not interpret
them as installed constraints. See [current status](limitations.md).

A runnable two-schema recipe is provided in
[examples/sqlite](https://github.com/asqueel-org/asqueel/tree/main/examples/sqlite).
