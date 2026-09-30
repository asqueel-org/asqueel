# Read data through application tables

Start with a database built from a `SqlDatabaseConfig` recipe. All examples on
this page use the `sales.customer`, `sales.invoice` and `sales.line` model in the
[tutorial](tutorial.md). They assume its physical tables and seed data exist.
Each example explicitly commits on success and rolls back on failure, including reads.

## Select, filter and order

```python
try:
    invoice = db.table("sales.invoice")
    rows = invoice.query(
        columns="$id, @customer.name AS customer_name, $total",
        where="$total >= :minimum",
        params={"minimum": 100},
        order_by="$total DESC, $id",
        limit=20,
    ).fetch()
    db.commit()
except Exception:
    db.rollback()
    raise

```

`rows` is a list of dictionaries. With the tutorial data it contains one invoice:
`{'id': 10, 'customer_name': 'Ada', 'total': Decimal('125.00')}`.
The decimal value comes from PostgreSQL numeric adaptation; it is not a float.

A query is lazy. Constructing it validates some options but does not execute
SQL; model references and expressions are compiled when you inspect or execute
it. Each `.fetch()` or `.execute()` compiles and executes again.

| Option | Meaning and default |
|---|---|
| `columns` | Projection string or sequence; `'*'` by default. |
| `where` | Trusted SQL predicate using model references and value parameters. |
| `params` | Mapping of bound values. `sqlparams` is also accepted. |
| `order_by` | SQL ordering expression using model references. Overrides the model’s default table ordering. |
| `limit`, `offset` | Nonnegative integers; `limit=0` returns no rows. |
| `for_update` | `False`; when true, lock base-table rows until transaction completion. |
| `exclude_draft` | `True`; applies a declared draft policy. |
| `exclude_logical_deleted` | `True`; also accepts `False` or `'mark'`. |
| `ignore_partition` | `False`; enforce declared partition scopes. |

The table is chosen by `db.table(...)`, not by a query option. Short names such
as `'invoice'` work only when unambiguous. Use qualified names in reusable code.
[Row policies](row-policies.md) explains the last three options. Their camel-case
spellings `excludeDraft`, `excludeLogicalDeleted` and `ignorePartition` are also
accepted; do not supply both spellings of the same option.

## Read the expression vocabulary

| Syntax | Meaning | Example |
|---|---|---|
| `$name` | Local logical column, including a declared virtual column. | `$total >= :minimum` |
| `@relation.column` | Column on a declared to-one target. | `@customer.name` |
| `AS name` | Result dictionary key. | `$id AS invoice_id` |
| `:name` | Bound data value. | `params={'minimum': 100}` |
| `:env_name` | Explicit parameter, or environment fallback for `name`. | `:env_customer_id` |
| SQL expression | Trusted PostgreSQL expression. | `COALESCE($total, 0) AS amount` |

A direct column keeps its logical name. A relation projection defaults to a
path-derived name such as `_customer_id_name`; prefer explicit `AS` when defining
a public result shape. Give computed projections explicit aliases for clarity.
Result names must be unique.

For unusual logical column names use `$"display name"`; double embedded quotes,
as in `$"a""b"`. Result aliases containing spaces also need double quotes.
Quoted SQL strings, comments, quoted identifiers and dollar-quoted bodies protect
their contents from reference expansion.

`*` follows the model's physical/static-column selection rules. Choose dynamic
virtual columns explicitly when they belong in the result. Prefer explicit projections for lists and other stable interfaces:
new formulas can otherwise change both the output and the cost of a query.

## Bind values, including collections

```python
try:
    rows = db.table("sales.customer").query(
        columns="$id, $name",
        where="$name ILIKE :pattern",
        params={"pattern": "%ad%"},
        order_by="$id",
    ).fetch()
    db.commit()
except Exception:
    db.rollback()
    raise

```

Parameters bind values, not identifiers or SQL fragments. Choose ordering and
column expressions from application-controlled options. Do not interpolate
external values into SQL. Missing parameters raise an error; unused entries in
an explicit `params` mapping are omitted from the compiled statement.

The shorthand `query(where='$id=:wanted', wanted=1)` is supported. Unknown
keywords that are not consumed as parameters fail, helping catch misspelled
query options. Prefer the explicit mapping for reusable application code.

For PostgreSQL list membership, use `ANY` with a Python list:

```python
try:
    rows = db.table("sales.customer").query(
        columns="$id, $name", where="$id = ANY(:ids)",
        params={"ids": [1, 2]}, order_by="$id",
    ).fetch()
    db.commit()
except Exception:
    db.rollback()
    raise

```

An empty array matches no rows. For the PostgreSQL `ANY` expression, use a cast
such as `:ids::bigint[]` if the surrounding SQL cannot infer the array type.
Lists containing `None` retain PostgreSQL NULL semantics. Genro's collection
binding syntax also supports `IN :ids` and `NOT IN :ids`: the compiler prepares
the required bindings rather than interpolating values into the SQL text.

Use `IS NULL` for a NULL test. `column = :value` with `value=None` does not mean
`IS NULL`. PostgreSQL casts such as `:minimum::numeric` are preserved.

## Navigate relations without writing joins

```python
try:
    rows = db.table("sales.invoice").query(
        columns="$id, @customer.name AS customer_name",
        where="@customer.name = :name", params={"name": "Ada"},
        order_by="$id",
    ).fetch()
    db.commit()
except Exception:
    db.rollback()
    raise

```

The relation is declared by the model, and its target must be a recognized
primary or unique key. The compiler creates a LEFT JOIN and reuses it for the
same path across projections, filters and ordering. A missing target produces
NULL values. A WHERE condition on the target can still exclude that row.

Several to-one relations can be chained, using `@customer.@country.name` or
`@customer.country.name` when those relations exist. Reverse paths describe
collection relationships: choose their cardinality and result shape explicitly. Related-table policies are not automatically added to a
plain join; the root table's policies govern the query.

## Use relations, formulas and aggregates

```python
try:
    rows = db.table("sales.invoice").query(
        columns="$id, @customer.name AS customer_name, $double_total, $line_total, $has_lines",
        order_by="$id",
    ).fetch()
    db.commit()
except Exception:
    db.rollback()
    raise

```

`customer_name` is the result name for the related column `@customer.name`;
`double_total` is a SQL expression; `line_total` and `has_lines` are correlated
formulas. Their declaration and scope rules are in [models](models.md) and
[formulas](formulas.md). They are read-only.

For a count, use an explicit SQL aggregate:

```python
try:
    rows = db.table("sales.invoice").query(columns="COUNT(*) AS n").fetch()
    count = rows[0]["n"]
    db.commit()
except Exception:
    db.rollback()
    raise

```

Use `query.count()` when you want the count of a query result. Use `group_by`,
`having` and `distinct` to express grouping and uniqueness. Counting grouped
results is different from counting base rows: define the query shape before
choosing its terminal. An SQL aggregate does not assemble related collections;
those have an explicit result shape.

## Fetch exactly one record

```python
try:
    customer = db.table("sales.customer")
    reader = customer.record(1)
    first = reader.output("dict")
    again = reader.output("dict")  # A copy of the same cached snapshot.
    immediate = customer.record(2, mode="dict")
    db.commit()
except Exception:
    db.rollback()
    raise

```

`record()` enforces exactly one visible match. It raises `RecordNotFoundError`
for no match and `RecordMultipleRowsError` for several. It is not a `fetch()[0]`
shortcut that silently ignores additional rows.

Supply a complete key mapping or an ordered sequence for composite primary keys.
A scalar is accepted for a single-column key, including zero. Key values cannot
be `None`. Alternatively, supply `where` and `params` for a unique selector.
Record reads select the complete resolved row; custom projections, `limit` and
`offset` are rejected. Use `query()` for partial rows.

`reader.refresh()` discards and reloads its snapshot in the current environment.
A reader does not automatically refresh after a write, commit or scope change.
Choose a record output for the consumer: dictionary data, a Bag representation
or serialized data. A Selection adds result operations and metadata around a
query result, rather than turning a table into a tracked row object.

## Inspect SQL and result metadata

```python
query = db.table("sales.invoice").query(
    columns="$id, $total", where="$id=:wanted", params={"wanted": 10},
)
compiled = query.compiled  # No connection required.
print(compiled.sql)
print(dict(compiled.params))

try:
    result = query.execute()
    assert result.rows[0]["id"] == 10
    assert [column.name for column in result.columns] == ["id", "total"]
    db.commit()
except Exception:
    db.rollback()
    raise

```

`QueryResult` has `rows`, `rowcount` and `columns`. Direct model projections carry
dtype, UI and source identity metadata. Arbitrary SQL expressions do not acquire
inferred dtype or UI metadata. Results are fully materialized; pagination limits
memory use when fetching large datasets.

`compiled.sql` is prepared for the driver, not for Python string interpolation.
Parameters may contain sensitive application data; log selectively. For direct
execution and parameter formatting, see [the compiler interface](compiler.md).

## Lock rows during a change

```python
try:
    row = db.table("sales.customer").record(1, for_update=True).output("dict")
    db.table("sales.customer").update({"id": row["id"], "name": "Ada Lovelace"})
    db.commit()
except Exception:
    db.rollback()
    raise

```

PostgreSQL locks only the base table with `FOR UPDATE OF`. Locks end at commit or
rollback. A cached reader does not acquire a new lock in another transaction;
use a fresh reader or refresh it. PostgreSQL rejects locking incompatible SELECT
forms, including aggregate projections.

Next: [write data](writes.md), [understand transactions](transactions.md), or
[diagnose a query](troubleshooting.md).
