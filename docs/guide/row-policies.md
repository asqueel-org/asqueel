# Row visibility and partition scopes

Row policies declare default visibility and partition behavior on a table.
The compiler applies them when producing model-based queries. They are separate
from database privileges and PostgreSQL row-level security: raw SQL and direct
connections do not acquire these policies automatically.

The supported policies are logical partition scopes, draft visibility, and
logical deletion. Logical partition scopes add query predicates; they do not
create PostgreSQL partitions or route queries to other databases.

## Declare policies in a model

```python
from asqueel import SqlDatabaseConfig, AsqueelDb


class Documents(SqlDatabaseConfig):
    def main(self, root):
        table = root.db("documents", conninfo="dbname=example").schemas().schema(
            "app",
        ).tables().table(
            "document", pkey="id",
            x_partition={
                "field": "organization_id",
                "current": "organization",
                "allowed": "allowed_organizations",
                "include_null": True,
            },
            x_draft_field="draft",
            x_logical_deletion_field="deleted_at",
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

Partition fields must resolve to physical columns. Their `current` and `allowed`
entries name [environment keys](environment.md), not data values. `allowed` is
optional; `include_null` defaults to `True`.

Use `x_partitions=[{...}, {...}]` for multiple dimensions. Do not combine
`x_partition` and `x_partitions`. Each dimension has its own field and environment
keys; their predicates are combined with AND.

Inspection does not infer policies from suggestive database column names. Add
application policies explicitly to an imported model. See [importing](importing.md).

## Query within an environment scope

Application tables apply these policies automatically through the database's
shared environment:

```python
# db comes from a recipe declaring the app.document policy above.
with db.temp_env(organization=0):
    try:
        documents = db.table('app.document').query(columns='$id, $title', order_by='$id').fetch()
        db.commit()
    except Exception:
        db.rollback()
        raise

```

This SELECT restricts `organization_id` to `0`, includes only rows whose draft
field is not true, and includes only rows whose deletion marker is NULL.
`0` is a valid current value; it is not treated as missing.

Policy conditions and your explicit `where` are individually parenthesized and
joined with AND. A user condition containing OR therefore cannot escape the
partition restriction through operator precedence.

## Partition semantics

Presence is determined by whether an environment key exists, rather than the
truth value of its contents.

| Context for one dimension | Resulting restriction |
|---|---|
| Current key present with a non-NULL scalar | Field equals that value. `0`, `False`, and `''` remain valid values. |
| Current key present with `None` | Field IS NULL. |
| Allowed key present with an empty collection | FALSE: no rows match. |
| Allowed key present with nonempty values | Field belongs to those values; NULL handling is described below. |
| Both current and allowed keys present | Both restrictions apply: their intersection. |
| Neither key present | Compilation raises `ValueError`. |

Values must be appropriate for the database column's type. Allowed values must
be a collection of scalars, such as a list or tuple. A string, mapping, scalar
`None`, or nested collection is not an allowed-values collection.

For a nonempty allowed collection, `include_null=True` also admits NULL rows.
With `include_null=False`, NULL rows are admitted only when the collection
explicitly contains `None`. An empty collection always matches no rows,
regardless of `include_null`.

```python
with db.temp_env(allowed_organizations=[10, 20]):
    # With include_null=True: organization_id IN (10, 20) OR organization_id IS NULL.
    query = db.table('app.document').query(columns='$id')
    print(query.sqltext)

with db.temp_env(organization=10, allowed_organizations=[20]):
    # The current value is outside the allowed set, so the SELECT matches no rows.
    query = db.table('app.document').query(columns='$id')
    print(query.sqltext)

with db.temp_env(allowed_organizations=[]):
    query = db.table('app.document').query(columns='$id')
    print(query.sqltext)  # Matches no rows.
```

These examples assume that `db.environment` has no default current organization. Temporary
scopes overlay existing values; they do not remove an inherited current key.
Assigning `None` requests NULL rows rather than removing the key.

`ignore_partition=True` explicitly bypasses partition predicates and their
required context:

```python
query = db.table('app.document').query(columns='$id', ignore_partition=True)
print(query.sqltext)
```

It does not disable draft or logical-deletion filtering. The same option exists
on insert, update, delete, soft_delete, and restore; expose it only where your
application intends to allow that behavior.

### Relational partition fields

A partition may use a declared to-one path, for example `@organization.region`.
SELECT resolves the relation and applies the root table's partition condition
to the reached field. The relation must have a recognized unique target key.

This does not automatically apply the target table's own draft, deletion, or
partition policies. A missing target yields NULL; it can therefore match a
NULL-accepting scope.

Writes on a table with a relational partition are rejected unless
`ignore_partition=True` is explicitly supplied. The compiler does not silently
substitute an unguarded write for a relational guard.

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

## Guarded writes

Partition policies apply to insert, update, and physical delete. Draft and
logical-deletion read filters do not automatically apply to these operations.

For INSERT, a missing partition column is filled from its current environment
value, including `None`. With only an allowed set and no current value, the
insert must provide that column explicitly. Provided values must satisfy both
the current and allowed restrictions; out-of-scope values raise `ValueError`.

For UPDATE, the existing row is restricted by the partition predicate. If the
update changes a partition column, its new value is checked against the same
scope. An explicit empty allowed collection matches no existing rows and
cannot be used to insert a new row. A supplied out-of-scope replacement value
is rejected before execution.

```python
with db.temp_env(organization=10):
    # Compile only, without executing a write.
    created = db.compiler.insert(
        'app.document', {'id': 100, 'title': 'Draft', 'draft': True},
    )  # organization_id is filled with 10.
    print(created.sql, dict(created.params))
```

Here `db.compiler` is used explicitly to inspect the generated write before
executing anything. Ordinary application calls to `table.insert()` and
`table.update()` execute immediately.

A SQL guard that matches no rows produces a normal zero-row update/delete;
it is not an authorization exception. Update and delete still require an
explicit predicate. `where='TRUE'` means every row allowed by the partition
scope, unless that scope is explicitly bypassed.

## Soft deletion and restoration

Soft deletion is an UPDATE with an explicit non-NULL marker value. Restoration
sets the marker to NULL. Neither operation adds draft/deletion read filters;
both retain the normal partition write guards.

```python
from datetime import datetime, timezone

with db.temp_env(organization=10):
    try:
        document = db.table('app.document')
        deleted = document.soft_delete(
            value=datetime.now(timezone.utc),
            where='$id = :id', sqlparams={'id': 100},
            returning='$id, $deleted_at',
        )
        restored = document.restore(
            where='$id = :id', sqlparams={'id': 100},
            returning='$id, $deleted_at',
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

```

These table methods execute immediately in the shared transaction. They require
an existing row to affect any data. `document.delete(...)` remains a physical
DELETE even when the model declares a logical-deletion field.

See [environment scopes](environment.md) for query reuse checks and
[transactions](transactions.md) for grouping changes atomically.
