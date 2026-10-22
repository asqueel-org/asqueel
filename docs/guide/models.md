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
        name_long='Customer name',
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
    table.indexes().index(name='invoice_total', columns={'total': 'DESC'})
    return table


class SalesModel(SqlDatabaseConfig):
    def main(self, root):
        tables = root.db('sales_app').schemas().schema(
            'sales', sqlname='public',
        ).tables()
        customer_table(tables)
        invoice_table(tables)


builder = SalesModel()
builder.create()
model = builder.render().model

assert model.table('sales.invoice').sqlname == 'invoice'
assert model.table('sales.invoice').sqlschema == 'public'
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

Queries use qualified names such as `sales.invoice`. The live table exposes
`sqlschema` and `sqlname`; its physical columns expose `sqlname`.
Native packages declare `sqlschema` and `sqlprefix`; a table or column can declare
`sqlname`. A package prefix defaults to the package name, following the legacy.
The source-to-migration projection uses these same objects.

## Keep descriptive attributes on the column

Labels and the other attributes the grammar declares stay on their model node:

```python
column = model.table('sales.customer').column('name')
label = column.attributes.get('name_long')
dtype = column.dtype
```

Use source contributions to override declarations before rendering. The removed
`resolve_model(..., ui=...)` overlay and separate column `.config` wrapper are
not part of the live model. Declared attributes remain available in
`attributes`; validation attributes are exposed separately by `validations`.
An attribute the element does not declare raises, naming the attribute and the
element: free extras such as `x_ui_label` are outside this release's grammar.

## Declare relations and formulas

The relation above is navigable as `@customer_id.name`: a forward relation is
named by its owning column. `x_name` does not rename the forward path.

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

### Redefine a virtual column

Declaring the same virtual column with a different kind replaces its definition,
as in the legacy model. Attributes not redefined by the new declaration remain:

```python
virtuals.aliasColumn('customer_name', '@customer_id.name',
                     dtype='T', name_long='Customer')
virtuals.formulaColumn('customer_name', "'from_formula'")
```

`customer_name` is now a formula; `relation_path` is removed, while `dtype='T'`
and `name_long='Customer'` remain. Reversing the declarations produces an alias
and removes `sql_formula`. The column keeps its position and group, with no
duplicate node. The same rule applies through `colgroup` and when composing
ordered configuration contributions. Composing recipes does not mutate the
input recipes.

Only the defining attributes of the former kind are removed. Accessory
attributes, including `static`, `required_columns`, `var_*` and named `select_*`
declarations, remain unless explicitly overridden, as in the legacy cleanup.
Retained attributes do not activate the former kind. Existing conflict rules
for repeated declarations of the same kind remain unchanged. Physical↔virtual
replacement is still rejected.

`aliasColumn` names an existing column reached through a relation, following the
legacy model's target-and-override behavior:

```python
# Add inside invoice_table(), before returning; reuse its virtuals handle.
virtuals.aliasColumn(
    'customer_name', relation_path='@customer_id.name', name_long='Customer name',
)
```

Read the alias as `$customer_name` in projections, filters, ordering or another
formula. Its dtype and descriptive metadata are inherited from the destination;
non-None local attributes take precedence. Its own identity is
preserved in result metadata. The target may itself be an alias or a formula.
For multiple relations, both legacy `@customer_id.@country_id.name` and
`@customer_id.country_id.name` are accepted. Local `name`/`$name` alias targets are also
accepted as a native convenience. Cycles and missing targets raise errors.

With a rendered application, `db.table('sales.invoice').column('customer_name')`
returns the live hierarchical column object. Its `attributes['relation_path']`
preserves the declaration. Effective dtype and metadata are resolved from the
target when no local value is declared; there is no `originalColumn` handle.
Inherited `notnull` metadata describes the target column; a LEFT JOIN can still
produce NULL when the source record has no related row.

An alias of a column that has a relation also inherits that relation during
model rendering. This is an approved extension to the legacy behavior:

```python
# invoice.customer_id already relates to customer.id
row.aliasColumn('customer_id', '@invoice_id.customer_id')
# The row can now query @customer_id.name.
```

The inherited relation is weak: no physical column, foreign key or supporting
index is created for the alias. Its own declared relation takes precedence:

```python
row.aliasColumn('customer_id', '@invoice_id.customer_id').relation('other_customer.id')
```

Relations on virtual columns default to weak. The target key is inherited,
not the original owner's inverse name, inverse cardinality or lifecycle actions.
Alias chains follow the effective relation, including explicit overrides.
This does not enable virtualRelation declarations or to-many query operations.

Aliases are read-only and never become physical columns in migration output.
An alias key in a write mapping is skipped without error: it never becomes an
SQL column. The write cycle reads back with RETURNING only the physical columns
whose value the database decides; aliases are never returned. The model distinguishes
physical/static columns from dynamic virtuals when expanding SELECT `*`.
Virtual relations describe model relationships derived from queries or conditions;
their cardinality remains part of their contract.

See [Queries](queries.md) for projections, parameters and relation traversal,
and [Row policies](row-policies.md) for explicit partition, draft and deletion
metadata. Policy attributes belong on tables. A subtable supplies a named logical
subset; a store selects a database context. Neither is a physical partition.

## Read resolved metadata or save a recipe

`model.table('sales.invoice')` returns the `DbTableObj` owned by the hierarchical
model. The operational `db.table('sales.invoice').model` is that same object.
`columns` contains physical nodes, `virtual_columns` contains virtual nodes,
and `relations` is the legacy relation Bag. Descriptive attributes and option
nodes remain in this hierarchy. `pkey` is the logical key name.

`model_to_json(model)` and `model_from_json(document)` save and restore the
hierarchy as version 2 `asqueel-model` JSON. The restored model is unbound and
can be passed to `SqlDatabase(model=model, config=config)`, a compiler or physical
projection. Connections are not included. Attributes must contain JSON values;
Python classes, callbacks and other executable/runtime objects raise `TypeError`.
Keep those in the source recipe. Loading never imports classes or executes code.
The old descriptor JSON format is rejected explicitly.

Use `SqlMigrationRenderer(to_physical_builder(model))` for migration JSON.

`SqlPythonEmitter` emits an editable Python module from a built recipe:

```python
from asqueel import SqlPythonEmitter

source = SqlPythonEmitter(builder).emit(class_name='GeneratedSalesModel')
# Save source in your application if you want to maintain the emitted recipe.
```

Use the original recipe when saving semantic and UI metadata. A recipe produced
by the [physical migration bridge](migrations.md) contains only the physical
schema and is not a replacement for your application model.
