# Dialects, drivers and catalog providers

Use `PostgresCompiler` and `PostgresDatabase` for the standard PostgreSQL path.
The lower-level adapters let applications separate query planning, SQL syntax,
parameter binding and database I/O. PostgreSQL with psycopg 3 is the implemented
data backend; adapter protocols do not imply support for additional databases.

## Assemble the PostgreSQL pipeline

Given a resolved `model`, the explicit pipeline is equivalent to the PostgreSQL
compiler facade:

```python
from asqueel import PostgresDialect, PsycopgDriver, QueryCompiler
from asqueel import Database, SqlEnvironment


def find_customer(model, conninfo, customer_id):
    environment = SqlEnvironment()
    driver = PsycopgDriver()
    compiler = QueryCompiler(
        model, PostgresDialect(), driver, environment=environment,
    )
    query = compiler.select(
        'customer', where='$id = :customer_id',
        params={'customer_id': customer_id},
    )
    with Database(conninfo, driver=driver, environment=environment) as db:
        return db.execute(query)
```

Constructing a compiler or formatting a query does not connect to PostgreSQL.
The psycopg package is imported only when the driver connects or executes.

## Inspect the boundaries

Each stage has a different responsibility:

| Stage | Input and output | Responsibility |
|---|---|---|
| `QueryCompiler` | Model and query arguments → `QueryPlan` | Resolve model fields, relations, policy predicates and contextual values. |
| `DataDialect` | `QueryPlan` → `SqlStatement` | Render SQL syntax and quote identifiers. |
| `BindingFormatter` | `SqlStatement` → `CompiledQuery` | Produce driver placeholders and the corresponding parameter map. |
| `SyncDriver` | Connection and `CompiledQuery` → `QueryResult` | Execute, materialize results and expose connection/transaction operations. |
| `Database` | Application operations → driver calls | Own transaction lifecycle and enforce thread ownership and environment checks. |

For debugging or tooling, stop after planning:

```python
from asqueel import PostgresCompiler


def inspect_query(model):
    compiler = PostgresCompiler(model)
    plan = compiler.plan_select('customer', columns='$id', limit=10)
    statement = compiler.dialect.render(plan)
    compiled = compiler.formatter.prepare(statement)
    return plan, statement, compiled
```

`compile_plan(plan)` combines rendering and formatting. The compiler rejects a
plan for a different dialect, and compiler construction rejects incompatible
dialect/formatter profiles.

## Binding without parsing SQL again

`SqlStatement.parts` contains strings and `Parameter` nodes. Identifiers have
already been quoted by the dialect. Only parameter nodes become placeholders:

```python
from asqueel import PsycopgDriver
from asqueel.query_plan import Parameter, SqlStatement

statement = SqlStatement(
    ('SELECT 12 % 5 AS remainder WHERE ', Parameter('enabled')),
    {'enabled': True},
)
query = PsycopgDriver().prepare(statement)

assert query.sql == 'SELECT 12 %% 5 AS remainder WHERE %(enabled)s'
assert dict(query.params) == {'enabled': True}
```

For the `postgresql/psycopg_named` profile, literal percent characters in text
are doubled for psycopg. Parameter nodes become `%(name)s`; values are never
interpolated into SQL. Repeated parameters share a value. Unused supplied
parameters are omitted; missing parameters, invalid parameter names and unknown
statement-part types raise errors.

Prepare the original statement once per output. `prepare()` accepts
`SqlStatement`, not an already prepared `CompiledQuery`; repeated preparation
of the same original statement produces identical output.

### Direct compiled SQL

`CompiledQuery(sql, params, columns)` defaults to the PostgreSQL/psycopg profile.
Its SQL is already driver-ready and is not rewritten. Supply psycopg named
placeholders and escape literal `%` as `%%`, even when the parameter map is
empty. Use separate parameter values rather than string interpolation.

If you provide result-column metadata, its names, number and order must match
the actual result columns. The driver checks before fetching; mismatches and
metadata supplied for a statement without a result set raise errors. Matching
metadata retains its declared type, UI information and provenance.

Dialect/binding profile mismatches are rejected before connection acquisition.
Profile validation does not parse arbitrary direct SQL or apply model policies
to it. Direct SQL remains trusted application code.

## Implement an adapter

The interfaces live in these modules:

- `asqueel.dialects.base.DataDialect`: `name`, `capabilities`,
  `quote_identifier(name)`, `tokens(expression)` and `render(plan)`.
- `asqueel.drivers.base.BindingFormatter`: `dialect`, `binding` and
  `prepare(statement)`.
- `asqueel.drivers.base.SyncDriver`: the formatter contract plus `validate`,
  `connect`, `execute`, `commit`, `rollback` and `close`.

The compiler's expression resolution uses the dialect tokenizer to distinguish
code from strings, identifiers and comments. A dialect must preserve those
boundaries as well as render the plan correctly; changing placeholder syntax
alone does not implement a new dialect.

An alternative driver should validate its query profile, preserve the statement's
result metadata and environment binding, materialize results before returning,
and leave transaction ownership to `Database`. Return the original driver
exception when an operation fails. The runtime uses synchronous driver methods
on the calling thread.

Use `Database(driver=...)` for a generic adapter. `PostgresDatabase(driver=...)`
accepts only the `postgresql/psycopg_named` profile. A compatible profile label
is a contract to implement and test, not automatic proof of compatibility.

## Catalog import is a separate interface

`CatalogProvider.inspect(connection, schemas, ui=...)` reads database structure.
It is separate from data SQL rendering and does not own the supplied connection
or transaction. `PostgresCatalogProvider` implements PostgreSQL inspection;
`inspect_postgres(...)` is its convenience facade.

```python
import psycopg
from asqueel import PostgresCatalogProvider


def inspect_application_schema(conninfo):
    with psycopg.connect(conninfo) as connection:
        result = PostgresCatalogProvider().inspect(connection, ['public'])
    return result.model, result.warnings
```

Inspect the warnings before treating an imported model as complete. Catalog
import cannot reconstruct application-only UI or Python behavior. Migration
rendering and application remain separate from both catalog inspection and
query execution; a catalog provider does not make a new backend migratable.

See [low-level transactions](low-level-runtime.md) for lifecycle rules and
[current limitations](limitations.md) before implementing against an extension seam.
