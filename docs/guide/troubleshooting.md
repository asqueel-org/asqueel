# Diagnose common problems

Start by identifying the stage that failed: configuration/rendering, compilation,
execution or transaction completion. Compilation does not contact PostgreSQL;
successful compilation does not prove that the physical schema or arbitrary SQL
expression is valid on the server.

## Inspect the query you intended to run

```python
query = db.table("sales.invoice").query(
    columns="$id, $total", where="$id=:wanted", wanted=10,
)
compiled = query.compiled
print(compiled.sql)
print(dict(compiled.params))
print([column.name for column in compiled.columns])
```

If the table has a partition policy, enter the required `db.temp_env(...)` scope
before compiling. Parameters may contain private data; do not blindly publish
logs. Use the SQL and parameter mapping together when reproducing a statement;
do not interpolate the mapping into SQL yourself.

## Configuration and model errors

| Symptom | What to check |
|---|---|
| Unknown or ambiguous table | Use its fully qualified logical name; inspect `db.model.tables`. |
| Unknown column/relation | Use model names rather than physical names. A relation defaults to the owning column's name unless `x_name` overrides it. |
| Duplicate collection or declaration | Reuse the handle returned by `columns()` / `virtual_columns()`; compose before resolving. |
| Invalid relation target | The target must exist in the complete model and have a recognized primary/unique key. `one_one` is not proof of uniqueness. |
| Layer does not override the expected value | Layers need the same root label and matching declaration paths. Read through `.config(...)`. |
| Missing config value | `None` means missing in the config read stack; use `default=` for optional reads. |
| Declaration fails to render | Check the effective grammar, reference targets and the renderer diagnostic. |

Building a database does not create tables. A server error such as “relation does
not exist” often means the model's physical schema/table has not been created,
or its physical-name mapping differs from the existing database.

## Unexpected rows or values

| Symptom | Explanation and next step |
|---|---|
| No rows despite a matching WHERE | Check partition context and draft/deletion filters; policies are combined with WHERE. |
| An allowed set returns nothing | `allowed=[]` intentionally matches no rows; current and allowed restrictions intersect. |
| Missing related values | Traversal is a LEFT JOIN; an absent target returns NULL. |
| A related filter removes a base row | A WHERE condition on a joined target must still be true; LEFT JOIN does not override it. |
| A formula total includes deleted/draft rows | Formula subqueries include these by default. Set `excludeDraft=True` / `excludeLogicalDeleted=True` in the definition. |
| Empty SUM is NULL | This is PostgreSQL aggregate behavior. Use an explicit `COALESCE` when zero is intended. |
| Scalar subquery returns multiple rows | Choose an aggregate or explicit ordered `limit=1`; no implicit limit is added. |
| `IN :ids` fails | Collection expansion is absent. Use PostgreSQL `= ANY(:ids)` and a list. |
| Changes to a fetched dictionary are not saved | Results are data. Pass writable fields to `table.update(...)`. |
| An updated record reader shows old data | `SqlRecord` caches its snapshot. Call `refresh()` or construct a new reader. |
| SELECT `*` becomes expensive or gains fields | It includes virtual columns; choose an explicit projection. |

## Transaction and lifecycle errors

| Symptom | Explanation and recovery |
|---|---|
| Writes disappear after leaving `with db:` | Closing rolls back pending work. Use `db.commit()` / `db.rollback()` or explicit `db.commit()`. |
| Cannot enter a transaction scope | A prior read or write may already have opened a pending transaction. Complete it deliberately first; nested scopes are not supported. |
| Connection is rollback-only | A table/shared write hook failed or rollback failed. Roll back explicitly; ordinary SQL execution errors already trigger automatic rollback. |
| `EnvironmentMismatchError` | A saved compiled statement captured different context. Recompile within the intended scope or use a lazy query terminal there. |
| `RecordNotFoundError` | No visible record matched, or a hooked write failed to identify its row. Review the selector and scope. |
| `RecordMultipleRowsError` | A record read or hooked update/delete matched more than one row. Fix the selector; do not hide matches with a limit. |
| Thread ownership error | Share the DB, not its internal connection records or driver connections. Each worker must release its own connections. |
| `DatabaseClosedError` | Construct a new database; closed objects cannot be reopened. |
| Commit outcome is `unknown` | The server outcome was not confirmed. Reconcile using application identifiers before retrying. |

Driver exceptions such as `psycopg.errors.UniqueViolation` propagate unchanged.
Catch those you can handle **outside** the transaction block. A Python hook's
external side effects are not undone by a SQL rollback.

## Import or migration refuses a model

Read the warnings in `result.warnings` and `model.warnings`. Querying supported imported tables and reproducing the complete
schema are different guarantees. A migration projection rejects warnings and
structures it cannot faithfully represent. Do not remove metadata or clear
warnings merely to get past validation.

Check [importing](importing.md) for catalog coverage and [migrations](migrations.md)
for naming fidelity, projection limits and command preparation.

## Prepare a useful bug report

Include the installed Asqueel version, Python/PostgreSQL versions, a minimal
recipe, the API call and full exception, plus relevant generated SQL and sanitized
parameters. State whether the issue occurs without execution. Describe the
expected rows and the actual result, including NULL and empty-collection cases.
A small disposable schema is easier to reproduce than a complete application.
