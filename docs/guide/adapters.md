# Dialects, drivers and catalog providers

The SELECT compiler follows the [single hierarchical pipeline](compiler.md).
PostgreSQL uses `PostgresDialect` and `PsycopgDriver`; SQLite uses `SqliteDialect`
and `SqliteDriver`.

| Boundary | Responsibility |
| --- | --- |
| `QueryCompiler` | Resolve fields, relations, formulas, aliases and parameters against DbModel. |
| `SqlCompiledQuery` | Hold resolved SELECT clauses and result metadata. |
| `dialect.compile_sql()` | Assemble SQL clauses and apply backend syntax. |
| `driver.prepare_sql(sql, kwargs, snapshot)` | Prepare placeholders and binding values, without a connection. |
| `db.execute(compiled)` | Execute on the selected connection and transaction. |

For inspection, use `db.compiler.plan_select('sales.invoice', columns='$id')`;
`db.compiler.compile_plan(plan)` returns the executable `CompiledQuery`.
Driver/dialect mismatches are rejected.

For SQL already constructed by an adapter, the shared boundary is:

```python
def execute_sql(db, sql, kwargs):
    compiled = db.driver.prepare_sql(sql, kwargs, db.environment.snapshot())
    return db.execute(compiled)
```

There are no structured `SqlStatement` or `Parameter` nodes. The existing legacy
text preparation handles bindings; it does not validate untrusted SQL.

Catalog providers perform read-only introspection. Their serialized snapshots
are distinct from the live model; migration uses the physical projection and
asqueel-migration. The SELECT dialect does not implement schema migration.
