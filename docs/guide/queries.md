# Querying and changing data

For application code, build a database from [configuration](configuration.md)
and use its table objects:

```python
# db is a SqlDatabase built from your application recipe.
with db.transaction():
    customer = db.table('sales.customer')
    customer.insert({'id': 1, 'name': 'Ada'})
    rows = customer.query(columns='$id, $name', where='$id=:wanted', wanted=1).fetch()
    customer.update({'id': 1, 'name': 'Ada Lovelace'})
```

`query()` is lazy and each `fetch()` executes again. Table writes share the
database session and return `QueryResult`; they do not commit individually.
`update(record)` uses the complete declared primary key to identify the row;
use an explicit `where` and `params` to change a key. `delete(key)` physically
deletes the selected row; soft deletion is a separate operation.

Writes return physical columns by default (`returning='*'`). Request a simple
SQL formula explicitly when needed. Structured subquery formulas must be read
with a separate query. Value mappings must contain writable columns; passing a
fetched row containing virtual columns directly to `update()` is not supported.

Use `query(..., for_update=True)` or `record(key, for_update=True)` inside a
transaction to lock the base-table rows until commit or rollback. PostgreSQL
`FOR UPDATE OF` targets only the base table, including when the query joins other
tables. Aggregate projections and other SQL forms that PostgreSQL cannot lock
are rejected by the server; NOWAIT, SKIP LOCKED and other lock modes are not
provided by this API. A cached record output does not acquire a new lock after
the original transaction ends; use a fresh record or `refresh()` in the new
transaction.

## Compiler and low-level execution examples

The remaining examples expose the components used internally by `SqlDatabase`.
`PostgresCompiler` turns model-based queries into SQL and bound parameters;
`PostgresDatabase` executes them synchronously. Its standalone `execute()` commits
each operation, unlike the shared application session. Compilation does not
connect to a database, create tables, or apply migrations.

This page uses a small resolved model. You can obtain the same kind of model
from [builder declarations](models.md) or [database inspection](importing.md).

```python
from genro_sql import (
    Column, PostgresCompiler, Relation, ResolvedModel, Table,
)

customer = Table(
    'customer', schema='sales', pkey=('id',),
    columns={
        'id': Column('id', 'I'),
        'name': Column('name', ui={'label': 'Customer'}),
    },
)
invoice = Table(
    'invoice', schema='sales', pkey=('id',),
    columns={
        'id': Column('id', 'I'),
        'customer_id': Column('customer_id', 'I'),
        'total': Column('total', 'N'),
        'note': Column('note'),
        'doubled_total': Column('doubled_total', 'N', formula='$total * 2'),
    },
    relations={
        'customer': Relation(
            'customer', 'sales.customer', ('customer_id',), ('id',),
        ),
    },
)
model = ResolvedModel({customer.key: customer, invoice.key: invoice})
compiler = PostgresCompiler(model)
```

## Select rows

```python
query = compiler.select(
    'sales.invoice',
    columns='$id, @customer.name AS customer_name, $total',
    where='$total >= :minimum',
    params={'minimum': 100},
    order_by='$id',
    limit=20,
    offset=0,
)

assert [column.name for column in query.columns] == [
    'id', 'customer_name', 'total',
]
```

The main arguments are:

| Argument | Meaning |
|---|---|
| `table` | Logical `schema.table` name; a short table name is accepted only when unambiguous. |
| `columns` | A comma-separated string or sequence of projection expressions. Defaults to `'*'`. |
| `where` | A trusted SQL expression with Genro column references and named data parameters. |
| `params` | A mapping of parameter names to Python values. |
| `order_by` | A trusted ordering expression, such as `'$total DESC, $id'`. |
| `limit`, `offset` | Nonnegative integers. `limit=0` returns no rows. |
| `exclude_draft` | Defaults to `True`; applies a declared draft policy. |
| `exclude_logical_deleted` | `True`, `False`, or `'mark'`; defaults to `True`. |
| `ignore_partition` | Defaults to `False`; `True` explicitly bypasses declared partition filters. |

See [row policies](row-policies.md) for the last three options. If a table has a
partition policy, its required [environment](environment.md) must be available
even when the query's explicit `where` already restricts that column.

### Column references and names

`$total` names a logical column in the selected table. The compiler uses the
model's physical schema, table, and column names and quotes them separately.
Application queries therefore do not need to embed naming prefixes.

For logical names containing spaces, punctuation, or non-ASCII characters, use
`$"display name"`. Double an embedded double quote: `$"a""b"` refers to the
logical name `a"b`. The same syntax works in projections, filters, ordering, and
formulas. Wildcards also handle these names.

A direct projection retains its logical name unless you provide `AS`:

```python
query = compiler.select(
    'sales.invoice',
    columns='$id AS invoice_id, $total AS amount',
)
```

Computed SQL expressions require an explicit alias:

```python
query = compiler.select(
    'sales.invoice',
    columns='COALESCE($total, 0) AS amount',
)
```

Aliases must be unique. An alias containing spaces must be quoted, for example
`'$total AS "Invoice amount"'`. `*` expands all declared columns, including
formula columns; it is not forwarded as a database wildcard.

### Relations

`@customer.name` resolves the model relation named `customer`, then its target
column `name`. The relation target must have a recognized unique key for the
join columns. Traversal uses a LEFT JOIN and reuses that join when the same path
appears in projections, filters, and ordering. Multiple declared relation
segments can be chained.

A missing related row therefore produces NULL target values. A target condition
placed in `where`, such as `@customer.name = :name`, still excludes rows where
that condition is not true; the LEFT JOIN does not override your filter.

Without an explicit alias, `@customer.name` is returned as `customer_name`.
Relation path segments currently use ASCII identifier names. This syntax does
not implement inverse one-to-many collections or arbitrary join declarations.

### Parameters, literals, and expressions

```python
query = compiler.select(
    'sales.invoice',
    where='$note ILIKE :pattern AND $total >= :minimum',
    params={'pattern': '%overdue%', 'minimum': 0},
)
```

Values are bound separately from SQL. Missing referenced parameters raise
`ValueError`; unused supplied parameters are omitted from the executable query.
`:env_name` can fall back to an environment value, as described in
[the environment guide](environment.md).

Use `IS NULL` for a NULL test; binding `None` to an equality expression does not
change SQL's NULL comparison rules. PostgreSQL casts such as `:minimum::numeric`
are preserved. SQL strings, quoted identifiers, dollar quotes, and comments
protect their contents from Genro reference expansion.

SQL expressions are trusted application code. Parameters bind data values;
they do not make user-supplied column names, operators, ordering clauses, or SQL
fragments safe. Choose such expressions from application-controlled options.
Do not interpolate values into `where` or `columns`.

### Formulas and aggregates

The model's `doubled_total` formula can be selected like any other column:

```python
query = compiler.select('sales.invoice', '$id, $doubled_total')
```

Formula references are expanded and cycles are rejected. A formula is read-only
for insert/update values.

An explicit SQL aggregate is supported as an expression:

```python
query = compiler.select('sales.invoice', 'COUNT(*) AS invoice_count')
```

This returns a normal compiled SELECT with the applicable read filters. There
is no separate `count()` method or `group_by`/`having` query option. Aggregate
SQL expressions do not enable automatic grouping, row deduplication, or collection
assembly. The `aggregateRows` option is rejected.

## Execute and read results

With the corresponding tables already present in PostgreSQL:

```python
from genro_sql import PostgresDatabase

with PostgresDatabase('dbname=myapp user=myapp') as db:
    result = db.execute(query)
    for row in result.rows:
        print(row)
```

`QueryResult.rows` is an eagerly materialized list of dictionaries.
`QueryResult.rowcount` is the driver's affected/returned-row count, and
`QueryResult.columns` describes the result columns. For direct columns,
metadata includes the model dtype, UI metadata, and the stable column identity
in `source` when one is declared. Otherwise `source` is the logical column path.
Arbitrary computed expressions do not acquire inferred dtype or UI metadata.

Each `db.execute()` runs in its own transaction. For several statements that
must succeed together, use [an explicit transaction](transactions.md).

`query.sql` and `query.params` are available for diagnostics. The SQL is already
prepared for psycopg parameter binding: literal percent signs are doubled.
If executing directly through psycopg, always pass the mapping, even when empty:

```python
# `connection` is an existing psycopg connection owned by your application.
# connection.execute(query.sql, dict(query.params))
```

Do not use Python string interpolation or omit the mapping. Bound values may
contain application data; choose what to record in diagnostic logs accordingly.

## Insert, update, and delete

```python
inserted = compiler.insert(
    'sales.invoice',
    {'id': 10, 'customer_id': 2, 'total': 125, 'note': 'Initial invoice'},
    returning='$id, $total',
)
updated = compiler.update(
    'sales.invoice',
    {'total': 150},
    where='$id = :id',
    params={'id': 10},
    returning='$id, $total',
)
deleted = compiler.delete(
    'sales.invoice',
    where='$id = :id',
    params={'id': 10},
    returning='$id',
)
```

Keys in `values` are logical column names. Values are bound parameters, not SQL
expressions. Unknown columns and writes to formulas are rejected. Database
constraints still govern generated columns, identity columns, and other
server-side restrictions.

`returning` defaults to `'*'`; use `None` when no returned rows are needed. An
empty insert mapping emits DEFAULT VALUES, although partition policies may fill
in required columns first. Update needs at least one value. Update and delete
require a nonempty predicate; use `where='TRUE'` deliberately when all rows in
the active partition scope should be affected.

DML does not support relation traversal, including formulas in RETURNING that
need a join. Choose an explicit list of local returning columns in that case.
A subsequent SELECT can read the related/formula value.

`delete()` is a physical deletion. [Soft deletion and restoration](row-policies.md)
are separate operations. Declared partition guards apply to writes; draft and
logical-deletion read filters do not automatically restrict them.

## Supported expression scope

The compiler resolves column references, declared to-one relation paths,
formulas, aliases, and named parameters. It does not implement legacy macros,
Bag query input, virtualRelation declarations, record/selection APIs, or
store/tenant routing. Unsupported options raise errors rather than being
silently ignored. PostgreSQL SQL fragments remain PostgreSQL-specific even when
the surrounding model uses logical names.

Continue with [row policies](row-policies.md), [environment scopes](environment.md),
or [transactions](transactions.md).
