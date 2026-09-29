# Build a model from PostgreSQL

`inspect_postgres(connection, schemas, *, ui=None)` reads selected PostgreSQL
schemas and returns `ImportResult(model, warnings)`. It does not create, alter
or delete database objects and does not commit, roll back or close the supplied
connection. The connection must be a synchronous psycopg connection.

## Inspect explicit schemas

Install the PostgreSQL extra for database access:

```sh
pip install 'genro-sql[postgresql]'
```

Keep connection settings outside the recipe:

```python
import psycopg
from genro_sql import inspect_postgres


def load_model(dsn):
    with psycopg.connect(dsn) as connection:
        connection.execute(
            'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'
        )
        result = inspect_postgres(connection, ['sales'], ui={
            'sales.customer.name': {'label': 'Customer name'},
        })
    return result
```

The example owns its new connection and uses a read-only transaction for the
catalog snapshot. When passing an existing connection, its transaction and
snapshot remain your responsibility. Pass a nonempty sequence of schema names,
not a single string. A requested schema that does not exist produces a warning.

Both logical and physical names initially match the database. The importer
does not infer packages, strip table prefixes or identify application row
policies from column names.

## Examine the result before using it

```python
from genro_sql import PostgresCompiler


def imported_query(result):
    for warning in result.warnings:
        print(warning)
    customer = result.model.table('sales.customer')
    for column in customer.columns.values():
        print(column.name, column.dtype, column.attributes.get('raw_type'))
    return PostgresCompiler(result.model).select(
        'sales.customer', columns='$name', order_by='$name',
    )
```

Warnings also appear in `result.model.warnings`. They do not prevent querying
the ordinary tables that were imported. They **do prevent projecting the
model for migrations**: a partial catalog must not be presented as a complete
desired schema. See [Migrations](migrations.md).

The importer currently records:

| Catalog information | Location in the model |
|---|---|
| Ordinary tables and columns | `model.tables`, `table.columns` |
| Primary-key columns, including composite keys | `table.pkey` |
| Foreign keys whose targets were imported | `table.relations` |
| Defaults, nullability, identity/generated information and column comments | `column.attributes` |
| Original PostgreSQL type | `column.attributes['raw_type']` |
| Constraint details and definitions | `table.attributes['constraints']` |
| Index definitions, ordering, predicates and options used by validation | `table.attributes['indexes']` |

Common types are normalized to Genro codes, for example `integer` → `I`,
`bigint` → `L`, and `character varying(120)` → `A` with size metadata. The original
type is retained. Unknown types remain verbatim and produce a warning rather
than being converted to an unrelated type.

Imported relations use the foreign-key **constraint name** as their navigable
name. If a constraint is named `invoice_customer_fk`, the corresponding query
path is `@invoice_customer_fk.name`. A foreign key pointing outside the imported
tables remains in constraint metadata and produces a warning; it is not a
navigable relation in that model.

## Preserve application information on reimport

A database catalog does not contain your UI labels, formulas, partition context
or application intent. Keep UI overlays under application control and pass the
same overlay on every import:

```python
from genro_sql import inspect_postgres

CUSTOMER_UI = {
    'sales.customer.name': {'label': 'Customer name', 'placeholder': 'Full name'},
}


def refresh_model(connection):
    return inspect_postgres(connection, ['sales'], ui=CUSTOMER_UI)
```

The importer does not persist the overlay itself. Its default column identity
is the physical `schema.table.column` path, so rename handling and overlay
updates are explicit application responsibilities. Define application
[policies](row-policies.md) deliberately; an imported `draft` or `deleted_at`
column does not activate filtering automatically.

## Understand the limits

Views, materialized views, foreign tables, inherited/partitioned tables and
partitions are not imported as queryable tables in this profile. Sequences,
application triggers, routines, row-level security and external FK targets are
reported as unsupported or unmanaged. The importer is not an inventory of all
PostgreSQL objects: roles, grants and extended dependencies are not modeled.

A preserved SQL definition is metadata, not proof that the migration bridge
can recreate it. In particular, generated columns, sequence-backed defaults,
custom collations and advanced indexes can be readable in the model while
remaining unsuitable for migration projection.

## Use the provider interface

For applications that inject adapters, the equivalent provider call is:

```python
from genro_sql import PostgresCatalogProvider


def inspect_catalog(connection):
    return PostgresCatalogProvider().inspect(connection, ['sales'])
```

`CatalogProvider` describes this read-only interface. The supplied provider
is PostgreSQL-specific; it is separate from the [data dialect](adapters.md)
that renders SELECT and DML. Importing legacy application packages is not
supported by this importer.
