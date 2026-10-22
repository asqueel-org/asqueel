# Compile queries without executing them

Asqueel has one live model and one SELECT compiler. `AsqueelDb`,
`build_database()` and the default configuration render construct the hierarchical
`DbModel`. Its tables own the operational `SqlTable` objects; relations are
resolved from the model's `relations` branch.

```python
from asqueel import SqlDatabaseConfig

source = SqlDatabaseConfig()
root = source.source.db('example', implementation='sqlite')
root.connection('main', database=':memory:')
table = root.packages().package('sales', sqlschema='main').table('invoice', pkey='id')
table.column('id', dtype='L')
table.column('total', dtype='N')

db = source.render()
query = db.table('sales.invoice').query(
    '$id,$total', where='$total >= :minimum', minimum=100,
)
compiled = query.compiled
sql, kwargs = compiled.sql, dict(compiled.params)
```

This example opens no connection. Compilation uses the environment current at
`.compiled`, `.fetch()` or `.count()`. The query can be reused without sharing
parameter manglers or table aliases between compilations.

## Compilation boundaries

1. `QueryCompiler.plan_select()` resolves fields, relations, formulas and
   parameters into `SqlCompiledQuery`, following the legacy recursion.
2. `SqlCompiledQuery.get_sqltext(adapter)` delegates clause assembly to
   `adapter.compileSql()`.
3. `QueryCompiler.compile_plan()` prepares the SQL and kwargs through
   `driver.prepare_sql()` and returns `CompiledQuery` with result metadata.
4. `db.execute(compiled)` executes on the owning connection and transaction.

`QueryCompiler.select()` combines steps 1–3. `plan_count()` and `count()` use the
legacy count algorithm. `PostgresCompiler(model)` selects PostgreSQL and psycopg
adapters for the same compiler; it is not another compilation path.

There is no `QueryPlan`, SQL `Fragment`, scanner-based SELECT compiler or
`driver.prepare(SqlStatement)` path. DML is developed separately and does not
belong in this SELECT compiler. Raw SQL can use the same `prepare_sql` /
`db.execute` execution boundary.

## Fields, relations and projections

The agreed references are `$column` and `@relation.column`. Logical quoted-field
syntax and advanced wildcards are not supported. `*` expands physical columns,
followed by declared static virtual columns. It omits X fields unless
`bagFields=True` or `for_update=True`. An explicit projection stays explicit.

Relations toward one use the legacy join resolution and aliases. Operations
on many relations are recognized as `@relation.operation(...)`; dispatch looks
for `many_operation`, and raises unsupported when absent. No handlers are
implemented and no exploding-row join is generated.

Native SQL formulas, aliases, dependencies, formula parameters, supported macros,
subqueries and bagItemColumn retain the tested legacy behavior. SQLite does not
emulate PostgreSQL XPath or JSON/XML aggregate formulas.

Missing ordinary bindings become SQL NULL during preparation. Symbolic WHERE
parameters follow legacy `embedFieldPars`; see [queries](queries.md#symbolic-parameters-and-external-values)
for external values and the existing escape convention.

## Record reads and locks

`query(...).fetchRecord()` executes the query and returns its single row.
`ignoreMissing=True` returns None for no row; otherwise missing or multiple
rows raise the corresponding record error. It applies the query filters like
every other terminal. Legacy `table.record()` is not available in this release.

`for_update=True` acquires locks only at execution. PostgreSQL uses
`FOR UPDATE OF t0`. SQLite uses `BEGIN IMMEDIATE` when no transaction is active;
in an existing transaction the driver issues a zero-row self-update on the
physical table to acquire the write reservation. Neither path commits,
opens a second connection or changes a row as part of lock acquisition.

## Model-only rendering and catalog snapshots

`source.render(mode='objects_tree')` and `resolve_model(source)` return the same
hierarchical model without binding an operational database. They use the same
walk/finalize construction as the default operational render.

`inspect_postgres`, `model_from_json` and authored recipes all return `DbModel`.
The SELECT and write compilers and physical migration projection consume that
same hierarchy. There is no descriptor graph or alternative projection path.
Operational rendering wraps the model in `SqlDatabase`; model-only rendering
leaves it unbound. These are two outputs of the same model construction.
