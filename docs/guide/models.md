# Define an application model

A `SqlDatabaseConfig` recipe declares tables and application metadata. Rendering
it produces a live database with a resolved `.model`. Building or resolving a
model does not create tables or open a connection. For a runnable application,
start with the [tutorial](tutorial.md); this page explains the declaration choices.

## Start with a recipe

```python
from asqueel import SqlDatabaseConfig, resolve_model


def customer_table(tables):
    table = tables.table('customer', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='L')
    columns.column(
        'name', dtype='T', notnull=True,
        x_identity='customer-name',
        x_ui={'label': 'Customer name'},
    )
    return table


def invoice_table(tables):
    table = tables.table('invoice', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='L')
    columns.column('customer_id', dtype='L').relation(
        'sales.customer.id', foreign_key=True, x_name='customer',
    )
    columns.column('total', dtype='N', size='12,2', notnull=True)
    virtuals = table.virtual_columns()
    virtuals.formulaColumn(
        'double_total', dtype='N', sql_formula='$total * 2',
    )
    table.indexes().index('invoice_total', columns={'total': 'DESC'})
    return table


class SalesModel(SqlDatabaseConfig):
    def main(self, root):
        tables = root.db('sales_app').schemas().schema(
            'sales', x_sql_schema='public', x_sql_prefix=True,
        ).tables()
        customer_table(tables)
        invoice_table(tables)


builder = SalesModel()
builder.create()
with builder.render() as db:
    model = db.model

assert model.table('sales.invoice').physical_name == 'sales_invoice'
assert model.table('sales.invoice').physical_schema == 'public'
```

The example uses caller-supplied integer primary keys. It does not allocate
IDs automatically. Common type codes include `L` for bigint, `I` for integer,
`T` for text, `A` for variable-length text, `N` for numeric, `B` for boolean,
`D` for date and `DHZ` for timestamp with time zone. For bounded text, use
`dtype='A', size='0:120'`; for decimal precision, use `dtype='N', size='12,2'`.

The functions above can live in separate Python modules. Call each function
with the same `tables` collection to compose the recipe. Construct the complete
model before resolving it so relation targets are available. Duplicate names
are errors; composition does not silently merge conflicting declarations.
Create a collection such as `columns()` once per parent and retain its handle
when several helper functions contribute to it.

## Keep logical and physical names separate

Use logical names such as `sales.invoice` in queries. The resolver supplies
the physical names to query rendering and the migration bridge.

| Attribute | Where to declare it | Meaning |
|---|---|---|
| `x_sql_schema` | Schema or table | Physical SQL schema; table overrides schema. |
| `x_sql_prefix=True` | Schema or table | Prefix table names with the logical schema plus `_`. |
| `x_sql_prefix='app_'` | Schema or table | Use this exact prefix. |
| `x_sql_prefix=False` | Schema or table | Disable an inherited prefix. |
| `x_sql_name` | Table or column | Exact physical name; on a table, it overrides the prefix. |

No convention is inferred from underscores. For example, an imported table
named `sales_invoice` remains named `sales_invoice` unless you explicitly
construct a different logical mapping. Physical table and column collisions
are rejected. PostgreSQL rendering also rejects identifiers exceeding 63 UTF-8
bytes instead of accepting server-side truncation.

## Attach UI metadata to the same column

`x_ui` keeps display information alongside the declaration. An overlay lets
you manage that information separately without creating a second column model:

```python
model = resolve_model(builder, ui={
    'sales.customer.name': {'placeholder': 'Enter a name'},
    'customer-name': {'label': 'Account name'},
})
column = model.table('sales.customer').columns['name']
assert column.ui['label'] == 'Account name'
assert column.ui['placeholder'] == 'Enter a name'
```

Precedence is inline `x_ui`, then the logical-path overlay, then the explicit
identity overlay. An identity defaults to `schema.table.column`; use
`x_identity` when it must remain stable after a logical rename. Stable identity
is metadata, not an automatic database-rename migration.

UI metadata cannot redefine the column type, formula, SQL name, nullability,
uniqueness or primary-key status. No GUI library is needed to resolve or query
the model. Labels, placeholders and formats are data for your application;
Asqueel does not instantiate editors or render forms.

## Declare relations and formulas

The relation above is navigable as `@customer.name`. Without `x_name`, its name
would be the owning column, giving `@customer_id.name`.

Relations in the native query profile navigate toward a declared primary or
unique key. `foreign_key=True` also makes the relation part of the physical
schema projection. A navigable relation without that flag does not create a
foreign key. Declaring `one_one` alone does not prove target uniqueness.
Inverse collections are not generated automatically.

`formulaColumn(sql_formula=...)` defines a read-only SQL expression. References
such as `$total` resolve against the model. Use trusted application SQL for the
formula; data values belong in query parameters. Structured `select`/`exists`
and named subqueries are described in [correlated formulas](formulas.md).
Python columns express application-side computations. Collection subqueries
represent related results with an explicit shape; they are distinct from scalar
formulas that return one value.

`aliasColumn` names an existing column reached through a relation, following the
legacy model's target-and-override behavior:

```python
# Add inside invoice_table(), before returning; reuse its virtuals handle.
virtuals.aliasColumn(
    'customer_name', relation_path='@customer.name', name_long='Customer',
    x_ui={'label': 'Customer name'},
)
```

Read the alias as `$customer_name` in projections, filters, ordering or another
formula. Its dtype and descriptive metadata are inherited from the destination;
non-None local attributes and UI overrides take precedence. Its own identity is
preserved in result metadata. The target may itself be an alias or a formula.
For multiple relations, both legacy `@customer.@country.name` and
`@customer.country.name` are accepted. Local `name`/`$name` alias targets are also
accepted as a native convenience. Cycles and missing targets raise errors.

With a rendered application, `db.table('sales.invoice').column('customer_name')`
is a stable live handle. Its `originalColumn` links to the target column and its
`relation_path` preserves the declaration. Configuration reads fall back to the
target when no local value is declared. `model.ui` exposes the merged UI metadata.
Inherited `notnull` metadata describes the target column; a LEFT JOIN can still
produce NULL when the source record has no related row.

Aliases are read-only and never become physical columns in migration output.
Writes with an alias in their value mapping fail explicitly. `RETURNING '*'`
includes only physical columns; explicitly returning an alias is supported only when its
expression is valid in the database's RETURNING clause. The model distinguishes
physical/static columns from dynamic virtuals when expanding SELECT `*`.
Virtual relations describe model relationships derived from queries or conditions;
their cardinality remains part of their contract.

See [Queries](queries.md) for projections, parameters and relation traversal,
and [Row policies](row-policies.md) for explicit partition, draft and deletion
metadata. Policy attributes belong on tables. A subtable supplies a named logical
subset; a store selects a database context. Neither is a physical partition.

## Read resolved metadata or save a recipe

`model.tables` is keyed by fully qualified logical names. `model.table('invoice')`
is also accepted when that short name is unambiguous. Tables expose `columns`,
`relations`, `pkey`, physical names and `policies`; columns expose `dtype`, `ui`,
`identity`, `formula` and `attributes`. Attributes retain source information and
provenance. Outer mappings are read-only; treat nested metadata as immutable too.

`SqlPythonEmitter` emits an editable Python module from a built recipe:

```python
from asqueel import SqlPythonEmitter

source = SqlPythonEmitter(builder).emit(class_name='GeneratedSalesModel')
# Save source in your application if you want to maintain the emitted recipe.
```

Use the original recipe when saving semantic and UI metadata. A recipe produced
by the [physical migration bridge](migrations.md) contains only the physical
schema and is not a replacement for your application model.
