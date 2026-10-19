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
`connection.options` supports `timeout` (default 20 seconds) and
`cached_statements` from `sqlite3`, and `foreignKeys` (default `True`).

Each connection runs `PRAGMA foreign_keys = ON`. `foreignKeys=False` runs
`PRAGMA foreign_keys = OFF` instead: SQLite then checks no foreign key on that
connection. Declare it as `connection(options={'foreignKeys': False})` or as
`connection.options().driver(foreignKeys=False)`. PostgreSQL refuses the option.

Logical schemas are attached files, as in GenroPy: each schema is the file
`<schema>.db` in the folder of the main file. `example.db` is the main file and
schema `app` uses `app.db` in the same folder. When the main file is missing,
its folder is created. Physical
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
Opening a SQLite runtime connection creates missing files and their folder, but
it does not create the declared tables.

`db.vacuum(table='')` runs `VACUUM` on `main` and on every attached schema,
then `ANALYZE [table]`, on a separate connection. `full` adds nothing on
SQLite, because `VACUUM` always rebuilds the file.

## Transactions and concurrency

Transactions are deferred, as in the legacy: the driver opens `BEGIN` before
the first INSERT, UPDATE or DELETE. Reads open no transaction and hold no lock,
so they block no other connection. The first write takes the database write
reservation; other connections can still read, and their writes wait until
explicit completion or until the timeout. `for_update=True` takes the write
reservation at the read: `BEGIN IMMEDIATE` when no transaction is open, a
zero-row self-update inside an open one. It is connection-level locking, not
PostgreSQL row locks.

The underlying semantics are documented by SQLite for
[transactions](https://www.sqlite.org/lang_transaction.html) and
[attached databases](https://sqlite.org/lang_attach.html). This first profile
protects a read/modify/write hook cycle only when it reads with `for_update`.
No lock upgrade, retry or savepoint policy is hidden in the driver.

## Supported scope and differences

The runtime supports parameterized CRUD, `RETURNING`, joins, formulas using
SQLite SQL, pagination, shared write hooks, raw commands, deferred callbacks
and rollback. Raw commands skip table triggers; they retain common DB hooks
and normal compiler/policy checks.

PostgreSQL-specific expressions such as `ILIKE`, `ANY`, array operations and
PostgreSQL casts are not translated into SQLite equivalents. Use expressions
valid for the configured backend. Values come back converted to the dtype, as in
the legacy: columns declared `date`, `time`, `timestamp`, `numeric` and
`boolean` return `date`, `time`, `datetime`, `Decimal` and `bool`. NUMERIC
values do not carry PostgreSQL's decimal precision guarantees. Decimal
parameters are passed as strings for SQLite affinity handling; dates and times
as ISO strings.

The migration adapter's limitations still apply, including unsupported foreign
key DDL and table alterations. SQLite cannot enforce foreign keys across attached
schemas. Logical relationships can still be used for queries; do not interpret
them as installed constraints. See [current status](limitations.md).

A runnable two-schema recipe is provided in
[examples/sqlite](https://github.com/asqueel-org/asqueel/tree/main/examples/sqlite).
