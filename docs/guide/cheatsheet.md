# Application API at a glance

This page is a lookup sheet after the [tutorial](tutorial.md). `db` is a live
`AsqueelDb`; `table = db.table('sales.customer')`. Physical tables must already
exist. Calls below are alternatives, not one script to execute in sequence.

## Objects and execution

| Task | API | Result / timing |
|---|---|---|
| Build from configuration | `AsqueelDb(Recipe, parents=[Base])` | `AsqueelDb`; no I/O. |
| Get a table | `db.table('sales.customer')` | Stable `SqlTable`; no I/O. |
| Get a column | `table.column('name')` | Stable `SqlColumn`; no I/O. |
| Read metadata | `table.column('name').model.ui` | Resolved UI mapping. |
| Read configuration | `table.config('pkey')` | Effective value from the shared handler. |
| Build a query | `table.query(columns='$id, $name')` | Lazy `SqlQuery`. |
| Inspect SQL | `query.sqltext` / `query.compiled` | Compiles; no I/O. |
| Read rows | `query.fetch()` | Executes; `list[NamedList]`, mutable rows with name/position access. |
| Read from a cursor | `query.execute()` | Executes; the open cursor, rows read by name. |
| Read one row | `query.fetchRecord()` | Executes; exactly one `NamedList` or an error; `ignoreMissing=True` returns None for no row. |
| Read keys, dicts, groups | `query.fetchPkeys()`, `fetchAsDict()`, `fetchGrouped()`, `fetchAsBag()`, `fetchAsJson()` | Executes; legacy fetch terminals. |
| Read in chunks | `query.iterfetch(arraysize=30)` | Executes on a server-side cursor; yields lists of rows. |

## Query options

```python
query = table.query(
    columns="$id, $name", where="$id >= :minimum",
    minimum=1, order_by="$id", limit=20, offset=0,
    for_update=False,
    exclude_draft=True, exclude_logical_deleted=True, ignore_partition=False,
)
```

Parameters are keyword arguments (`minimum=1`); `sqlparams={...}` takes a mapping
when names are built at runtime or clash with an option. Do not repeat a name in both. Camel-case policy options
are supported but cannot be combined with their snake-case equivalent.

`$column` references the model; `@relation.column` navigates a to-one relation;
`:value` binds data; `AS name` selects a result key. `#THIS` and `#name` belong to
the [formula](formulas.md) context, not a general public-query macro language.

## Writes

| Task | Call inside your transaction |
|---|---|
| Insert | `table.insert({'id': 3, 'name': 'Katherine'})` |
| Update by key | `table.update({'id': 3, 'name': 'Katherine Johnson'})` |
| Update with the old row | `table.update(record, old_record)` |
| Physical delete | `table.delete({'id': 3})` |
| Without triggers | `table.sql_insert(...)`, `table.sql_update(...)`, `table.sql_delete(...)` |
| Rows a query selects | `table.query(where=...).sql_update({...})`, `.sql_delete()` |
| Logical deletion | `table.update(dict(old, deleted_at=now), old)` |

`insert` and `update` return the record they received, modified by the cycle;
the `sql_*` query commands return the affected row count. Write values use
logical names without `$`. `delete` must remove exactly one row. See
[writes](writes.md) for the detailed contract.

## Lifecycle and context

```python
db = AsqueelDb(Recipe)
try:
    with db.tempEnv(organization=10):     # Context only; does not open a connection.
        try:
            db.table("app.document").insert({"id": 100, "title": "Example"})
            db.commit()
        except Exception:
            db.rollback()
            raise

finally:
    db.closeConnection()

```

Use `db.commit()` / `db.rollback()` for explicit completion.
`db.closeConnection()` rolls back what was not committed; the database stays
usable. Outside a request, `with session(db, **env):` clears the context at
entry and calls `closeConnection()` at exit.
Even reads open transactions. Nested tempEnv scopes are supported; savepoints are not. A database can be shared
between threads; each worker must release its own connections.

## Defaults that matter

| Behavior | Default |
|---|---|
| SELECT projection | All resolved columns, including virtuals. |
| DML RETURNING | All physical columns, excluding virtuals. |
| Public SELECT draft/deletion filters | Exclude drafts and logically deleted rows. |
| Formula subquery draft/deletion filters | Include both unless overridden in the definition. |
| Partition handling | `current_<path>` first, then `allowed_<path>` (NULL included); missing context filters nothing. |
| Empty allowed partition set | No filter, as GenroPy. |
| Relation traversal | LEFT JOIN to a unique target; target policies are not automatically propagated. |
| Scalar subquery cardinality | No implicit limit; several rows cause a server error. |
| Query fetch reuse | Execute again. |
| Record output reuse | Cached until refresh. |

The [capability matrix](limitations.md), [Python API](../api.rst) and
[grammar reference](../grammar.md) provide deeper lookup.
