# Formulas with correlated subqueries

`formulaColumn` supports a SQL expression, a scalar `select` definition or an
`exists` definition. Structured definitions follow the legacy dictionary shape;
`#THIS` refers to the row owning the formula, including when that formula is
reached through a relation or an alias.

## Declare scalar and EXISTS formulas

```python
from genro_sql import SqlDatabaseConfig, build_database


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


with build_database(Accounting) as db:
    # Compiles without connecting. Physical tables must exist before fetch().
    print(db.table('app.invoice').query(columns='$id, $total, $has_lines').sqltext)
```

`$amount` and `$invoice_id` belong to the subquery's table. `#THIS.id` belongs to
the invoice. Reading `@invoice.total` from a line still correlates the formula
with its invoice, not with the line's id. Relation paths after `#THIS` are also
supported in the to-one profile.

A scalar subquery must project exactly one column. SQL expressions such as
`COUNT(*)`, `SUM($amount)` and `MAX($date)` need no explicit output alias inside
the definition. There is **no implicit LIMIT 1**: PostgreSQL raises a cardinality
error if a scalar subquery returns multiple rows, and the session then requires
rollback. No matching scalar row yields NULL; EXISTS yields False. Aggregates
retain their SQL behavior, including SUM over an empty set returning NULL.

`exists` defaults to a constant projection. Set `dtype='B'` explicitly; the model
does not infer a result type from arbitrary SQL. `table` and a nonempty `where`
are required; use `where='TRUE'` deliberately for an uncorrelated query.

## Combine named subqueries

Use `select_<name>` and `#<name>` in a formula expression:

```python
# virtuals is the invoice's virtual_columns collection.
virtuals.formulaColumn('total_above_minimum', dtype='N',
    sql_formula='COALESCE(#amount, 0)',
    select_amount=dict(table='app.line', columns='SUM($amount)',
        where='$invoice_id=#THIS.id AND $amount >= :minimum'))
```

A query may supply the parameter with `params={'minimum': 100}` or
`minimum=100`. Definitions may instead supply local `params` or `sqlparams`
mappings; local values override inherited values only in their subquery scope.
Duplicate names declared in both local mappings are rejected. Parameter names
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
| `ignorePartition` / `ignore_partition` | False | Enforce the subquery table's partition scope, including an error when required context is absent. |
| `excludeDraft` / `exclude_draft` | False | Include draft rows unless exclusion is requested. |
| `excludeLogicalDeleted` / `exclude_logical_deleted` | False | Include logically deleted rows unless exclusion is requested. |

Draft and deletion defaults follow the legacy subquery behavior, which differs
from ordinary public SELECT defaults. **Partition handling intentionally differs
from legacy's implicit bypass:** the native model retains explicit partition
semantics. Use `ignorePartition=True` only when that bypass is intended.

For a visible-rows total, declare both `excludeDraft=True` and
`excludeLogicalDeleted=True` in its definition. Conditions, order and parameters
belong to the subquery; outer query options do not silently replace them.

## Options and current boundaries

Definitions accept `table`, `columns`, `where`, `params`/`sqlparams`, `order_by`,
`limit`, `offset`, the policy options above, and `cast`. Explicit `limit=1` with
an order is supported when the application intentionally selects one row.
`cast='numeric(14,2)'`, for example, casts the scalar result. Cast names use a
restricted SQL type syntax; quoted custom type names are not currently supported.

The compatibility values `subtable='*'`, `addPkeyColumn=False` and
`ignoreTableOrderBy=True` are accepted; other values are unsupported. They do not
add subtable behavior, implicit primary-key projection or a table default order.
Unknown options, including currently unsupported GROUP BY/HAVING/DISTINCT, fail
explicitly.

String definitions naming `subquery_*` methods, `sql_formula=True` callbacks,
`var_*`/formula variants, Python columns, and the separate `subQueryColumn`
collection API remain unimplemented. Do not confuse a formula with a scalar
subquery with automatic to-many collection shaping or virtualRelation.

Computed columns are read-only and excluded from physical migration output and
from DML `RETURNING '*'`. Explicit simple SQL formulas can still be returned by
DML; structured subquery formulas are currently limited to reads. Read them in a
separate query in the same transaction when needed after a write.
