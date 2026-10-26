# Direct SQL and compiled statements

For application code, use `AsqueelDb` with a configuration. Both direct SQL and
table operations go through `db.execute()` of a `SessionDb` and use the same
selected connection.

```python
from asqueel import AsqueelDb

shared = AsqueelDb('myapp')
with shared.session() as db:
    cursor = db.execute('SELECT :value AS value', {'value': 42})
    assert cursor.fetchone()['value'] == 42
    cursor.close()
    db.commit()
shared.close()
```

Direct SQL is trusted application code. Bind data through named parameters;
never interpolate values into SQL. The driver translates `:name` bindings
without altering placeholders inside strings, comments or quoted identifiers.
`:env_name` can resolve a value from the current environment unless an explicit
parameter overrides it. SQL expressions and functions must fit the backend.

`db.execute(sql, sqlargs=None, cursor=None, cursorname=None, autocommit=False,
dbtable=None, storename=None, _adaptArguments=True)` has the legacy signature
and returns the open cursor of the statement: `description`, `rowcount`,
`arraysize`, `fetchone()`, `fetchmany(size)`, `fetchall()`, iteration and
`close()`. Rows are `NamedList`, read by name or position, like the legacy dict
cursor. `cursorname` opens a server-side cursor on PostgreSQL (`'*'` generates
the name); SQLite ignores it. `autocommit=True` calls `db.commit()` after the
statement. `dbtable` is accepted. `storename`, `cursor` and
`_adaptArguments=False` raise `UnsupportedFeatureError`. A driver error raised
by execute or by a fetch rolls the connection back and is re-raised; the
database stays usable.

`db.execute(compiled_query)` also accepts a `CompiledQuery`, including the one
produced by `db.table(...).query(...).compiled`. Compiled queries already contain
their parameters and adapter profile (`dialect`, `binding`); do not pass a separate parameter
mapping. Environment bindings are checked before execution.

## Execution without a model

A caller that only executes statements builds an `AsqueelDb` from a recipe
that declares the `db` node and no package. Its sessions have the same lazy
connections, per-session state and explicit `commit()` / `rollback()`.

```python
from asqueel import AsqueelDb, SqlDatabaseConfig

config = SqlDatabaseConfig()
config.source.db('example', implementation='postgres', conninfo='dbname=example')
with AsqueelDb(config).session() as db:
    rows = db.execute('SELECT :value AS value', {'value': 42}).fetchall()
    db.commit()
```

There is no `transaction()` API. Unlike the former low-level runtime, `execute()`
does not open, commit and close a separate connection on every call. Callers
migrating from that API must add explicit completion.

`AsqueelDb(source, environment={...})` copies the supplied mapping into
the defaults of each new session. Savepoints and automatic retry are not
provided.

## Maintenance calls

- `db.analyze()` runs `ANALYZE` in the current transaction.
- `db.vacuum(table='', full=False)` reclaims storage on a separate connection:
  `VACUUM [FULL] ANALYZE [table]` on PostgreSQL; `VACUUM` then
  `ANALYZE [table]` on SQLite, where `full` adds nothing. `table` is the SQL
  table name. With pending work on any connection of the session,
  `vacuum` raises `TransactionStateError`: commit or roll back first.
- `db.setConstraintsDeferred()` defers the deferrable constraints until the
  commit of the current transaction (`SET CONSTRAINTS ALL DEFERRED` on
  PostgreSQL, `PRAGMA defer_foreign_keys = ON` on SQLite).
- `db.setLocale()` hands `currentEnv['locale']` to the adapter; neither adapter
  changes the connection.

See [transactions and database access](transactions.md) for errors, callbacks,
cleanup and connection selection.

### Parameter recognition in 0.7.0

A colon inside a SQL string, quoted identifier or comment is literal text:
`'doc:xyz' || :value` binds only `value`. The same rule applies inside formula
scopes and to `:env_name`. PostgreSQL dollar-quoted and `E` strings and nested
block comments are recognized; SQLite bracket/backtick identifiers are recognized.
Ordinary PostgreSQL strings assume `standard_conforming_strings=on`; use `E` for
backslash escapes. The historical `\:` escape remains supported.
