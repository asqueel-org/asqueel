# Application API at a glance

This page is a lookup sheet after the [tutorial](tutorial.md). `db` is a live
`SqlDatabase`; `table = db.table('sales.customer')`. Physical tables must already
exist. Calls below are alternatives, not one script to execute in sequence.

## Objects and execution

| Task | API | Result / timing |
|---|---|---|
| Build from configuration | `AsqueelDb(Recipe, parents=[Base])` | `SqlDatabase`; no I/O. |
| Get a table | `db.table('sales.customer')` | Stable `SqlTable`; no I/O. |
| Get a column | `table.column('name')` | Stable `SqlColumn`; no I/O. |
| Read metadata | `table.column('name').model.ui` | Resolved UI mapping. |
| Read configuration | `table.config('pkey')` | Effective value from the shared handler. |
| Build a query | `table.query(columns='$id, $name')` | Lazy `SqlQuery`. |
| Inspect SQL | `query.sqltext` / `query.compiled` | Compiles; no I/O. |
| Read rows | `query.fetch()` | Executes; `list[dict]`. |
| Read rows and metadata | `query.execute()` | Executes; `QueryResult`. |
| Read one row now | `table.record(1, mode='dict')` | Executes; exactly one dictionary or an error. |
| Cache one row | `reader = table.record(1)` then `reader.output('dict')` | Loads once; subsequent outputs are copies. |
| Refresh cached row | `reader.refresh()` | Executes again; returns reader. |

## Query options

```python
query = table.query(
    columns="$id, $name", where="$id >= :minimum",
    params={"minimum": 1}, order_by="$id", limit=20, offset=0,
    for_update=False,
    exclude_draft=True, exclude_logical_deleted=True, ignore_partition=False,
)
```

`sqlparams` is an alias input mapping; referenced keyword bindings are accepted.
Do not repeat parameter names across mappings/keywords. Camel-case policy options
are supported but cannot be combined with their snake-case equivalent.

`$column` references the model; `@relation.column` navigates a to-one relation;
`:value` binds data; `AS name` selects a result key. `#THIS` and `#name` belong to
the [formula](formulas.md) context, not a general public-query macro language.

## Writes

| Task | Call inside your transaction |
|---|---|
| Insert | `table.insert({'id': 3, 'name': 'Katherine'})` |
| Update by key | `table.update({'id': 3, 'name': 'Katherine Johnson'})` |
| Update by predicate | `table.update({'name': 'New'}, where='$id=:id', params={'id': 3})` |
| Physical delete | `table.delete(3)` |
| Choose returned columns | Add `returning='$id, $name'`. |
| Omit returned rows | Add `returning=None`. |
| Soft-delete a policy table | `document.soft_delete(marker, where='$id=:id', params={'id': 100})` |
| Restore a policy table | `document.restore(where='$id=:id', params={'id': 100})` |

All return `QueryResult`. Default RETURNING includes physical columns only.
Write values use logical names without `$`. A scalar or complete mapping selects
a single-column key; composite keys require all components. Hooked update/delete
requires exactly one row. See [writes](writes.md) for the detailed contract.

## Lifecycle and context

```python
db = AsqueelDb(Recipe)
try:
    with db.temp_env(organization=10):     # Context only; does not open a connection.
        with db.transaction():            # Commits on success, rolls back on error.
            db.table("app.document").insert({"id": 100, "title": "Example"})
finally:
    db.close()

```

Use `db.commit()` / `db.rollback()` for manual completion outside atomic scopes.
Even reads open transactions. No nested scopes/savepoints are provided. Construct,
use and close each database on the same thread.

## Defaults that matter

| Behavior | Default |
|---|---|
| SELECT projection | All resolved columns, including virtuals. |
| DML RETURNING | All physical columns, excluding virtuals. |
| Public SELECT draft/deletion filters | Exclude drafts and logically deleted rows. |
| Formula subquery draft/deletion filters | Include both unless overridden in the definition. |
| Partition handling | Enforce in outer queries and subqueries; missing required context errors. |
| Empty allowed partition set | Match no rows. |
| Relation traversal | LEFT JOIN to a unique target; target policies are not automatically propagated. |
| Scalar subquery cardinality | No implicit limit; several rows cause a server error. |
| Query fetch reuse | Execute again. |
| Record output reuse | Cached until refresh. |

The [capability matrix](limitations.md), [Python API](../api.rst) and
[grammar reference](../grammar.md) provide deeper lookup.
