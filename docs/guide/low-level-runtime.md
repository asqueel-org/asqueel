# Direct SQL and compiled statements

For application code, use `AsqueelDb` with a configuration. Both direct SQL and
table operations go through `db.execute()` and use the same selected connection.

```python
from asqueel import AsqueelDb

db = AsqueelDb('myapp')
try:
    result = db.execute('SELECT :value AS value', {'value': 42})
    assert result.rows == [{'value': 42}]
    db.commit()
finally:
    db.close()
```

Direct SQL is trusted application code. Bind data through named parameters;
never interpolate values into SQL. The driver translates `:name` bindings
without altering placeholders inside strings, comments or quoted identifiers.
`:env_name` can resolve a value from the current environment unless an explicit
parameter overrides it. SQL expressions and functions must fit the backend.

`db.execute(compiled_query)` also accepts a `CompiledQuery`, including the one
produced by `db.table(...).query(...).compiled`. Compiled queries already contain
their parameters and dialect/binding profile; do not pass a separate parameter
mapping. Environment bindings are checked before execution.

## Execution without a model

`Database(driver=...)` and `PostgresDatabase(...)` remain available for callers
that only execute statements. Their implementation is the same execution base
used by the configured DB: lazy named connections, thread-local state, and
explicit `commit()` / `rollback()`.

```python
from asqueel import PostgresDatabase

db = PostgresDatabase('dbname=example')
try:
    rows = db.execute('SELECT :value AS value', {'value': 42}).rows
    db.commit()
finally:
    db.close()
```

There is no `transaction()` API. Unlike the former low-level runtime, `execute()`
does not open, commit and close a separate connection on every call. Callers
migrating from that API must add explicit completion.

An explicitly supplied `SqlEnvironment` can be shared between a standalone
compiler and this execution facade. `AsqueelDb` instead copies its supplied
environment into per-thread defaults. Result rows are eagerly materialized;
streaming, savepoints and automatic retry are not provided.

See [transactions and database access](transactions.md) for errors, callbacks,
cleanup and connection selection.
