# Adapters

The SELECT compiler follows the [single hierarchical pipeline](compiler.md).
`db.adapter` adapts the database to its implementation: SQL
syntax, quoting, capabilities, connection, cursor and value conversion. There is
one adapter class per implementation; each module exposes `SqlDbAdapter`.

| `implementation` | Adapter |
| --- | --- |
| `'sqlite'` (default) | `asqueel.adapters.sqlite` |
| `'postgres'`, `'postgres3'` | `asqueel.adapters.postgres` (psycopg 3) |
| `'mysql'` | `asqueel.adapters.mysql` (PyMySQL, experimental, see [MySQL](mysql.md)) |
| `'<name>:<module>'` | `SqlDbAdapter` of `<module>` |

Any other name raises `ModuleNotFoundError`. With
`db.tempEnv(currentImplementation='postgres')`, `db.adapter` is the adapter of
that implementation, loaded on first use.

| Boundary | Responsibility |
| --- | --- |
| `QueryCompiler` | Resolve fields, relations, formulas, aliases and parameters against DbModel. |
| `SqlCompiledQuery` | Hold resolved SELECT clauses and result metadata. |
| `db.adapter.compileSql()` | Assemble SQL clauses and apply backend syntax. |
| `db.adapter.prepare_sql(sql, kwargs, snapshot)` | Prepare placeholders and binding values, without a connection. |
| `db.execute(compiled)` | Execute on the selected connection and transaction. |

For inspection, use `db.compiler.plan_select('sales.invoice', columns='$id')`;
`db.compiler.compile_plan(plan)` returns the executable `CompiledQuery`.
A `CompiledQuery` of another adapter profile is rejected.

For SQL already constructed by an adapter, the shared boundary is:

```python
def execute_sql(db, sql, kwargs):
    compiled = db.adapter.prepare_sql(sql, kwargs, db.environment_snapshot())
    return db.execute(compiled)
```

There are no structured `SqlStatement` or `Parameter` nodes. The existing legacy
text preparation handles bindings; it does not validate untrusted SQL.

Migration uses the physical projection of `DbModel` and asqueel-migration.
The adapter does not implement schema migration.

## SQL functions of the adapter

Table code can build formulas with these adapter functions:

| Function | PostgreSQL | SQLite |
| --- | --- | --- |
| `string_agg(field, separator)` | `string_agg(field, 'separator')` | `group_concat(field, 'separator')` |
| `unaccentFormula(field)` | `unaccent($field)` (needs the `unaccent` extension) | the field unchanged |
| `mask_field_sql(field, mode='2-4', placeholder='*')` | masking expression | masking expression |
| `ageAtDate(dateColumn, dateArg=None, timeUnit='day')` | age in `timeUnit` at `:dateArg` (default `:env_workdate`) | raises `UnsupportedFeatureError` |

`mask_field_sql` modes are `'email'`, `'creditcard'`, `'phone'` and `'N-M'`
(N characters visible at the start, M at the end); any other mode raises
`ValueError`.

```python
# <folder>/model/customer.py, in a package loaded with package(name, path=<folder>)
class Table:
    def config_db(self, pkg):
        customer = pkg.table('customer', pkey='id')
        customer.column('id', dtype='L')
        customer.column('email')
        customer.formulaColumn('masked_email', sql_formula=True)

    def sql_formula_masked_email(self, attr):
        return self.db.adapter.mask_field_sql('$email', mode='email')
```
