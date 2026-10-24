# Row visibility and partition scopes

Row policies declare default visibility and partition behavior on a table.
The compiler applies them when producing model-based queries. They are separate
from database privileges and PostgreSQL row-level security: raw SQL and direct
connections do not acquire these policies automatically.

The supported policies are logical partition scopes, draft visibility, and
logical deletion. Logical partition scopes add query predicates; they do not
create PostgreSQL partitions or route queries to other databases.

## Table attributes

`draftField`, `logicalDeletionField` and `partition_<field>` are table
attributes. `sysFields(draft=True)` supplies `draftField`;
enabled logical deletion supplies `logicalDeletionField`. SELECT uses these
declarations, never guesses policy from a column name. Read flags override
these filters as shown below.

Filters apply to the SELECT root, not automatically to joined tables. Formula
subqueries retain legacy defaults (include drafts/deleted rows, ignore partition)
and can explicitly override them.

## Declare policies in a model

```python
from asqueel import SqlDatabaseConfig, AsqueelDb


class Documents(SqlDatabaseConfig):
    def main(self, root):
        table = root.db("documents", implementation="postgres", conninfo="dbname=example").packages().package(
            "app", sqlschema="app", sqlprefix=False
        ).tables().table(
            "document", pkey="id",
            partition_organization_id="organization",
            draftField="draft",
            logicalDeletionField="deleted_at",
        )
        columns = table.columns()
        columns.column("id", dtype="I")
        columns.column("organization_id", dtype="I")
        columns.column("title", dtype="T")
        columns.column("draft", dtype="B")
        columns.column("deleted_at", dtype="DHZ")
```

Build with `db = AsqueelDb(Documents)` and close it when finished. The
following examples assume that live database and an existing physical
`app.document` table. Examples that inspect `query.sqltext` only compile and need no connection.
The examples using `fetch()` or table write methods execute against PostgreSQL.

A draft field must be a local physical boolean column. A logical-deletion field
must be a local physical nullable column, distinct from the draft field, and
cannot be part of the primary key. A non-NULL logical-deletion value means the
record is deleted; the value does not have to be boolean.

`partition_<field>='<path>'` partitions the table on the column `<field>`. The
value `<path>` names two [environment keys](environment.md): `current_<path>`
and `allowed_<path>`. Only the first `partition_*` attribute of a table counts.

## Query within an environment scope

Application tables apply these policies automatically through the database's
shared environment:

```python
# db comes from a recipe declaring the app.document policy above.
with db.tempEnv(current_organization=10):
    try:
        documents = db.table('app.document').query(columns='$id, $title', order_by='$id').fetch()
        db.commit()
    except Exception:
        db.rollback()
        raise

```

This SELECT restricts `organization_id` to `10`, includes only rows whose draft
field is not true, and includes only rows whose deletion marker is NULL.

Policy conditions and your explicit `where` are individually parenthesized and
joined with AND. A user condition containing OR therefore cannot escape the
partition restriction through operator precedence.

## Partition semantics

Values are read by their truth value.

| Environment | Resulting restriction |
|---|---|
| `current_<path>` true | `$<field> = :env_current_<path>`. |
| `current_<path>` false or absent, `allowed_<path>` true | `$<field> IS NULL OR $<field> IN :env_allowed_<path>`. |
| Neither true | No restriction. `0`, `False`, `''`, `None` and an empty collection add no filter. |

```python
with db.tempEnv(allowed_organization=[10, 20]):
    # organization_id IS NULL OR organization_id IN (10, 20).
    query = db.table('app.document').query(columns='$id')
    print(query.sqltext)
```

A fallback on an `__allowed_partition` column of the related table is
not available in this release.

`ignore_partition=True` explicitly bypasses partition predicates:

```python
query = db.table('app.document').query(columns='$id', ignore_partition=True)
print(query.sqltext)
```

It does not disable draft or logical-deletion filtering. Writes do not read
partitions, so the option has no write counterpart.

## Draft visibility

With a declared draft field, SELECT defaults to `exclude_draft=True` and adds
`draft IS NOT TRUE`. Both FALSE and NULL values remain visible.

```python
query = db.table('app.document').query(exclude_draft=False, ignore_partition=True)
print(query.sqltext)
```

The option is boolean. It does not change the stored draft value, and it does
not affect a related table's visibility. Writes are not filtered by draft
status, so an update can publish or edit an existing draft.

## Logical deletion and marking

With a declared deletion field, `exclude_logical_deleted` controls SELECT:

| Value | Behavior |
|---|---|
| `True` (default) | Adds `deleted_at IS NULL`. |
| `False` | Includes live and logically deleted rows. |
| `'mark'` | Includes both and appends the `_isdeleted` result column. |

```python
query = db.table('app.document').query(
    columns='$id, $title',
    exclude_logical_deleted='mark',
    ignore_partition=True,
)
```

`_isdeleted` contains the actual deletion value, such as a timestamp, or NULL.
Its metadata retains the deletion column's dtype and identity. It is not
converted into a boolean. The alias `_isdeleted` is reserved while marking.

Marking supports projections of physical local columns and physical columns
reached through to-one paths. Formulas and opaque SQL expressions, including
aggregates, are rejected in mark mode. If `*` includes a formula, use an explicit
physical-column list. For an aggregate that should include deleted rows, use
`exclude_logical_deleted=False` without requesting a marker.

## Writes and policies

Partition, draft and logical-deletion policies filter reads only.
`insert` does not fill the partition column from the environment, and `update`
and `delete` do not check that the row belongs to the current or allowed
partition ([#15](https://github.com/asqueel-org/asqueel/issues/15) proposes it).
Set the partition column in the record yourself.

## Logical deletion and restoration

There is no soft-delete command. Mark a row as deleted by writing its
logical-deletion column with `update()`, and restore it by writing `None`:

```python
from datetime import datetime, timezone

try:
    document = db.table('app.document')
    old = dict(document.query(where='$id = :id', id=100, for_update=True).fetchRecord())
    document.update(dict(old, deleted_at=datetime.now(timezone.utc)), old)
    db.commit()
except Exception:
    db.rollback()
    raise

```

The update runs the normal write cycle and its hooks. `document.delete(...)`
remains a physical DELETE even when the model declares a logical-deletion field.

See [environment scopes](environment.md) for query reuse checks and
[transactions](transactions.md) for grouping changes atomically.
