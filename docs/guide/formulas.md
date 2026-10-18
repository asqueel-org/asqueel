# Define computed columns and correlated formulas

`formulaColumn` supports a SQL expression, a scalar `select` definition or an
`exists` definition. Structured definitions follow the legacy dictionary shape;
`#THIS` refers to the row owning the formula, including when that formula is
reached through a relation or an alias.

## Choose an expression, an alias or a subquery

| Need | Declaration | Read it as |
|---|---|---|
| Calculate from fields in this row | `formulaColumn(sql_formula='$total * 2', ...)` | `$double_total` |
| Expose a related column with inherited metadata | `aliasColumn(relation_path='@customer_id.name', ...)` | `$customer_name` |
| Calculate one value from another table | `formulaColumn(select={...}, ...)` | `$line_total` |
| Test whether matching rows exist | `formulaColumn(exists={...}, dtype='B', ...)` | `$has_lines` |
| Combine several scalar subqueries | `sql_formula` plus `select_<name>` definitions | A single formula column |
| Collect related rows on PostgreSQL | `subQueryColumn(query={...}, mode='json')` or `mode='xml'` | A JSON array or XML text |

These are query-time expressions, not stored/generated database columns. They
are read-only in application writes and excluded from physical schema projection.
Set the dtype for expressions explicitly; arbitrary SQL does not infer it. An
alias inherits its target dtype and descriptive metadata, as described in [models](models.md).

For a first working example, use the [invoice tutorial](tutorial.md). This page
then expands the correlation and visibility rules you need for larger formulas.

## Declare scalar and EXISTS formulas

```python
from asqueel import SqlDatabaseConfig, AsqueelDb


class Accounting(SqlDatabaseConfig):
    def main(self, root):
        tables = root.db('accounting').schemas().schema('app').tables()
        invoice = tables.table('invoice', pkey='id')
        invoice.columns().column('id', dtype='I')
        columns = tables.table('line', pkey='id', x_draft_field='draft').columns()
        columns.column('id', dtype='I')
        columns.column('invoice_id', dtype='I').relation(
            'app.invoice.id', foreign_key=True, x_name='invoice')
        columns.column('amount', dtype='N')
        columns.column('draft', dtype='B')
        virtuals = invoice.virtual_columns()
        virtuals.formulaColumn('total', dtype='N', select=dict(
            table='app.line', columns='SUM($amount)',
            where='$invoice_id=#THIS.id',
        ))
        virtuals.formulaColumn('has_lines', dtype='B', exists=dict(
            table='app.line', where='$invoice_id=#THIS.id',
        ))


db = AsqueelDb(Accounting)
try:
    # Compiles without connecting. Physical tables must exist before fetch().
    print(db.table('app.invoice').query(columns='$id, $total, $has_lines').sqltext)
finally:
    db.close()

```

`$amount` and `$invoice_id` belong to the subquery's table. `#THIS.id` belongs to
the invoice. Reading `@invoice_id.total` from a line still correlates the formula
with its invoice, not with the line's id. Relation paths after `#THIS` are also
supported through ordinary relations. An inverse path can multiply rows in
the SELECT scope owning that path; no aggregation is added implicitly.

A scalar subquery must project exactly one column. SQL expressions such as
`COUNT(*)`, `SUM($amount)` and `MAX($date)` need no explicit output alias inside
the definition. There is **no implicit LIMIT 1**: PostgreSQL raises a cardinality
error if a scalar subquery returns multiple rows. Asqueel automatically rolls
back the pending transaction on that SQL error, including earlier pending writes. No matching scalar row yields NULL; EXISTS yields False. Aggregates
retain their SQL behavior, including SUM over an empty set returning NULL.

`exists` defaults to a constant projection. Set `dtype='B'` explicitly; the model
does not infer a result type from arbitrary SQL. `table` and a nonempty `where`
are required; use `where='TRUE'` deliberately for an uncorrelated query.

## Native package SQL formulas

Native package declarations now compile SQL expressions, dependencies on other
SQL formulas, ordinary forward/inverse relation paths and aliases through the existing compiler.
`var_*` supplies local bound values; the existing `parameters` mapping is also
accepted, with duplicate declarations rejected. For example:

```python
from asqueel import SqlDatabaseConfig, build_database

config = SqlDatabaseConfig()
pkg = config.source.db('formula_example').packages().package('sales')
line = pkg.table('line', pkey='id')
line.column('id', dtype='L')
line.column('amount', dtype='N')
line.formulaColumn('adjusted', '$amount * :factor', var_factor=2, dtype='N')
line.formulaColumn('combined', '$adjusted + :factor', var_factor=5, dtype='N')
line.aliasColumn('display_amount', '$combined')

with build_database(config) as db:
    compiled = db.table('sales.line').query('$id, $display_amount').compiled
    sql, kwargs = compiled.sql, dict(compiled.params)
    assert sorted(kwargs.values()) == [2, 5]
```

The two `factor` values belong to different formulas. A referenced formula uses
its own locals and query parameters, not its caller's locals. An alias follows
the target formula; it does not copy the target's executable attributes. Values
remain bindings, even when a string starts with `$` or `@`. Repeated compilation
creates fresh state and leaves both the model and application environment intact.

The compiler resolves fields and parameters using the selected dialect's scanner
and renderer; it does not translate arbitrary SQL functions between dialects.
For example, PostgreSQL INTERVAL expressions are not made portable to SQLite.

Native package `select`/`exists`/`select_*` declarations now use the same
correlated SELECT algorithm as the schema/table declarations below.
String references to subquery methods are resolved at compilation as described below.

## Formulas supplied by table methods

The legacy declaration `sql_formula=True` calls `sql_formula_<name>(attr)` on
the owning application table. Attach that table class with the existing
`x_table_class` option:

```python
from asqueel import SqlTable

class Invoice(SqlTable):
    def sql_formula_adjusted(self, attr):
        attr['var_factor'] = self.db.currentEnv.get('factor', 2)
        return '$amount * :factor'

# pkg is the package declared in your configuration.
invoice = pkg.table('invoice', pkey='id', x_table_class=Invoice)
invoice.column('id', dtype='L')
invoice.column('amount', dtype='N')
invoice.formulaColumn('adjusted', sql_formula=True, dtype='N')
```

The method runs during compilation, never during model rendering. It receives
an owned mutable copy of the column attributes and returns a nonempty SQL
expression. Changes to `var_*` and `select_*` are used in that compilation;
the source and model remain unchanged. Dependencies, aliases, subqueries and
parameter isolation use the same compiler path as declared SQL formulas.
Definitions are evaluated once per column in each compilation and reevaluated
when the query is compiled again. Methods are trusted application code and
must construct SQL without performing database I/O.

`SqlTable` supplies the legacy `__protecting_reasons` and `__invalid_reasons`
methods required by `sys_fields`, including NULL when no rules are declared
and empty text when none of the declared rules applies. These are result
formulas; they do not enforce write protections or implement diagnostics.
Standalone compilers without application tables cannot evaluate table methods.
RuntimeModel overlays are still pending.

## Combine named subqueries

Use `select_<name>` and `#<name>` in a formula expression:

```python
# virtuals is the invoice's virtual_columns collection.
virtuals.formulaColumn('total_above_minimum', dtype='N',
    sql_formula='COALESCE(#amount, 0)',
    select_amount=dict(table='app.line', columns='SUM($amount)',
        where='$invoice_id=#THIS.id AND $amount >= :minimum'))
```

A query may supply the parameter as `minimum=100` or with
`sqlparams={'minimum': 100}`. Definitions may instead supply a local `sqlparams`
mapping; local values override inherited values only in their subquery scope. Parameter names
are isolated during compilation so independent formulas cannot capture each
other's values. Values remain bound parameters, not SQL string substitutions.

A subquery may project another declared formula. Independent scalar aggregates
do not multiply rows in the outer query. Cyclic formula/alias dependencies raise
an error. Declared named subqueries must actually appear in SQL code: references
inside strings or comments do not count and are never expanded.

You must choose one of `sql_formula`, `select` or `exists` for a column. Use named
subqueries to combine scalar results in an explicit SQL formula. Ambiguous
combinations are rejected rather than silently selecting one definition.

## Scope and policy defaults

Each subquery uses the same environment snapshot as the outer compilation.
Environment dependencies from nested formulas are checked before execution.
A lazy application's next `fetch()` compiles again in its current environment.

| Option | Default inside a formula | Behavior |
|---|---|---|
| `ignorePartition` / `ignore_partition` | True | Legacy formula default: bypass partition. Set False to require the child table's partition context and filter. |
| `excludeDraft` / `exclude_draft` | False | Include draft rows unless exclusion is requested. |
| `excludeLogicalDeleted` / `exclude_logical_deleted` | False | Include logically deleted rows unless exclusion is requested. |

These defaults follow the legacy formula compiler and differ from ordinary
public SELECT defaults. The earlier Asqueel subquery path enforced partition
by default; it is now aligned with legacy for both native packages and the
schema/table path. Set `ignorePartition=False` explicitly when that filter
is required. This does not change the outer SELECT's partition default.

For a visible-rows total, declare both `excludeDraft=True` and
`excludeLogicalDeleted=True` in its definition. Conditions, order and parameters
belong to the subquery; outer query options do not silently replace them.

## Formula inputs and result shapes

A scalar select definition specifies its table, projection, predicate, parameters
and ordering. `group_by`, `having` and `distinct` use the same supported
clauses and checks as the outer SELECT. Use `limit=1` with an explicit order when the formula intentionally
selects one row. A cast specifies the SQL type of the scalar result. Policy and
subtable options belong to the subquery's own context.

Local `var_*` inputs are compiled as bound values. pyColumn computation remains
deferred.

## Native subQueryColumn

The existing native declaration uses the same child SELECT compiler and binding
scopes as scalar formulas. For example, on the native `invc.invoice` table:

```python
invoice.subQueryColumn('rows_json', query=dict(
    table='invc.invoice_row', columns='$product_id,$quantity,$unit_price',
    where='$invoice_id=#THIS.id'), mode='json')
invoice.subQueryColumn('notes_xml', query=dict(
    table='invc.invoice_note', columns='$note_type,$note_text',
    where='$invoice_id=#THIS.id'), mode='xml')
invoice.subQueryColumn('max_row_price', query=dict(
    table='invc.invoice_row', columns='MAX($unit_price)',
    where='$invoice_id=#THIS.id'), dtype='N')

# db is the database built from the configuration above.
compiled = db.table('invc.invoice').query(
    '$id,$rows_json,$notes_xml,$max_row_price').compiled
sql, kwargs = compiled.sql, dict(compiled.params)
```

With `mode=None` (the default), the column is a plain scalar subquery on
PostgreSQL and SQLite. Other modes except `json` and `xml` retain the legacy
plain SELECT behavior; `mode='sum'` does not synthesize SUM.

On PostgreSQL, `json` wraps the child SELECT in `jsonb_agg(row_to_json(...))`;
`xml` uses `xmlagg(xmlelement(..., xmlforest(...)))` cast to text. This follows
the corrected legacy implementation and supports explicit `distinct=True` on
the outer query. No automatic DISTINCT is added. JSON/XML modes on SQLite
raise an explicit unsupported-feature error before database I/O.

Ordering, limit, offset, grouping, HAVING and policies apply to the child SELECT
before aggregation. Use explicit aliases for expressions whose JSON keys or
XML element names matter. XML uses the resolved projection aliases and the
database's standard escaping; NULL XML fields are omitted, while JSON retains
them. An empty row source yields NULL in both modes, not an empty collection.
`var_*`, local `sqlparams`, relations, aliases and nested formulas reuse the
existing isolated scopes. `cast` on the row source of a JSON/XML aggregation
remains unsupported.

## Subqueries supplied by table methods

Existing declarations accept a method suffix instead of a query dictionary:
`select='total'`, `exists='matching'`, `select_total='total'`, or
`subQueryColumn(query='rows')` (plain or JSON mode). The compiler calls
`subquery_total()`, `subquery_matching()` or `subquery_rows()` with no arguments.
For example, using the existing application table class mechanism:

```python
class Invoice(SqlTable):
    def subquery_rows(self):
        return dict(table='invc.invoice_row', columns='MAX($unit_price)',
                    where='$invoice_id=#THIS.id')

# invoice is declared with x_table_class=Invoice.
invoice.formulaColumn('max_price', select='rows', dtype='N')
```

The method must return a mapping in the existing query shape. Its result follows
the same validation, correlation, policy, cast and parameter paths as an inline
dictionary. Copies protect mappings retained by application code. Methods run
only when the expression is compiled, can run more than once per compilation,
and are reevaluated on subsequent compilations. They are trusted Python code
and must construct declarations without database I/O.

The legacy lookup rule is significant: `subquery_*` belongs to the **current
SELECT's root table**, even when the formula is reached through a relation.
A nested SELECT has its own root. There is no fallback to the related table.
In contrast, `sql_formula_*` belongs to the formula's owning table. A SQL formula
method can set a `select_*` string in its local attributes; this uses the same
lookup rule. Parameter names stay isolated across the resulting subqueries.

Missing methods, invalid results and unbound standalone compilers report explicit
errors. RuntimeModel remains a separate integration: method results are not
stored in the model, and future overlays must give compiler and application
tables the same effective model. XML subQueryColumn still requires a query
dictionary, as in the legacy constructor; its string method form is not enabled.

A collection subquery returns related data with an explicit shape, rather than
a scalar. A virtual relation defines navigable model semantics. Keep those
contracts distinct even when both start from the same related table.

Computed columns are read-only and excluded from physical migration output and
from DML `RETURNING '*'`. Explicit simple SQL formulas can still be returned by
DML when their expression is valid there. A separate query in the same
transaction can obtain a computed view of the record after a write.

## Native bagItemColumn (PostgreSQL)

A native package can expose a scalar item from a Bag stored as XML, using the
existing legacy declaration:

```python
product.bagItemColumn('detail_weight', bagcolumn='$details',
                      itempath='specs.weight', dtype='N')
product.bagItemColumn('weight_unit', bagcolumn='$details',
                      itempath='specs.weight?unit', dtype='T')
```

Read these columns normally with `$detail_weight` and `$weight_unit`, including
in filters, ordering, aliases and supported subqueries. `bagcolumn` follows the
ordinary expression resolver, including `$` and `@` references. `itempath` uses
the legacy dotted Bag path: `#0` selects the first child, and a final `?attr`
selects an XML attribute. The resulting `/GenRoBag/...` XPath is a bound value
in the column's formula scope; columns and nested queries do not share its
parameter with one another or with the caller.

PostgreSQL takes the first XPath result, casts it to text, then to the declared
base dtype when required. Package custom types are resolved by the existing
model render (`money` in test_invoice_pg becomes `N`). Missing nodes, empty text
nodes and NULL XML yield NULL. Text retains XML escaping, as in the legacy;
there is no additional Python XML/Bag decoder. Invalid XML and failed casts
remain database errors at execution time.

SQLite has no corresponding legacy XPath implementation: selecting a
bagItemColumn raises `UnsupportedFeatureError` during compilation. Other
columns remain usable. This support does not implement the BAG/BAGCOLS macros,
pyColumn postprocessing or a new table-level helper API.
