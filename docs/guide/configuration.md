# Configuration and application objects

`SqlDatabaseConfig` declares connection settings and a SQL model in the same
Builders recipe. `build_database()` produces a synchronous `SqlDatabase` with
stable table, column and relation objects. Construction validates and binds the
model without connecting, executing SQL, or applying migrations.

## Build or render a recipe

```python
from genro_sql import SqlDatabaseConfig, build_database


class Shop(SqlDatabaseConfig):
    def main(self, root):
        database = root.db("shop", conninfo="dbname=shop")
        table = database.schemas().schema("sales").tables().table(
            "customer", pkey="id", name_long="Customers",
        )
        columns = table.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", x_ui={"label": "Name"})


db = build_database(Shop)
assert db.table("customer") is db.table("sales.customer")
assert db.table("customer").config("name_long") == "Customers"
db.close()

recipe = Shop()
recipe.create()
with recipe.render() as db:
    print(db.table("customer").query(columns="$id, $name").sqltext)
```

The default renderer is an object renderer. `render()` returns a database, not
DDL or serialized configuration. `target=False` is a string-renderer convention
and is not accepted here. Explicit delivery targets are not supported.

The root declares `name`, `implementation='postgresql'`, `conninfo=''`, and
optional `connect_kwargs`. An empty connection string uses the driver's normal
connection defaults when an operation is eventually executed. PostgreSQL is the
only supported implementation. `connect_kwargs={'autocommit': True}` is rejected.

`build_database(source, *, parents=None, driver=None, dialect=None,
environment=None)` accepts a recipe class, an existing builder instance, or a
configuration recipe file as supported by Builders' `ConfigHandler`. Recipe
classes and paths are instantiated by the handler. Existing instances are copied
before layers are merged; previously rendered live objects are not copied into
the new application.

## Layer configuration

Parent recipes provide the base; later parents and the final source override
matching paths through `ConfigHandler`. All layers must have the same single
root label. A childless higher-layer node does not erase the lower subtree.

```python
class Deployment(SqlDatabaseConfig):
    def main(self, root):
        root.db("shop", conninfo="host=localhost dbname=shop_test")


with build_database(Deployment, parents=[Shop]) as db:
    assert db.config("conninfo") == "host=localhost dbname=shop_test"
    assert db.table("sales.customer").config("pkey") == "id"
```

Configuration reads use the handler's read stack: written values, annotated
signature defaults, then the caller's explicit default. A missing value without
a default raises `KeyError`. `None` means missing in this stack; `False`, zero
and empty strings remain values.

```python
with build_database(Shop) as db:
    assert db.config("implementation") == "postgresql"
    customer = db.table("customer")
    assert customer.config("pkey") == "id"
    assert customer.column("name").config("dtype") == "T"
    assert customer.config("optional_hint", default=False) is False
```

`db.config` is the single global handler. Table and column views delegate to it
using their declaration paths. For example, `customer.config('pkey')` reads
`schemas.sales.tables.customer.pkey`. These views do not maintain independent
copies of configuration attributes.

Defaults from the effective grammar are resolved on a separate source copy before
building the semantic model. A mounted column grammar's default dtype therefore
also reaches `.model.dtype`; it is not merely a display-time configuration value.
The authored configuration remains unchanged. Standard SQL grammar declarations
and supported schema/table mounts can be used; the model still rejects unsupported
executable features. Builders 0.27 has a limitation with indirectly inherited
grammar overrides: use explicit grammar mixins and test the effective declaration
before relying on such overrides.

## Read and write through a table

Against an existing database with the example table:

```python
with build_database(Shop) as db:
    customer = db.table("customer")
    with db.transaction():
        customer.insert({"id": 1, "name": "Ada"})
        rows = customer.query(where="$id = :wanted", wanted=1).fetch()
        assert rows[0]["name"] == "Ada"
```

`query()` creates detached query intent; `.sqltext` compiles it, and `.fetch()`
executes it. Explicit `params={...}` is the clearest parameter interface.
`sqlparams` and referenced keyword parameters are also accepted; unused keyword
arguments fail rather than silently turning a misspelled option into a parameter.
Queries compile in the environment current at the terminal call.

`record(pkey)` returns a lazy exactly-one reader. `.output('dict')` returns a
copy of its cached result; `.refresh()` reloads it in the current environment.
`record(pkey, mode='dict')` is the immediate form. These APIs use ordinary Python
dictionaries. Legacy `Selection`, Bag output, and the `count()` terminal are not
implemented. Use an explicit aggregate projection for counting.

Insert, update, delete, soft-delete and restore return `QueryResult`. Read the
[transaction guide](transactions.md) before using writes: operations share a
session and do not commit individually.

## Add native table behavior

A table can select a `SqlTable` subclass with `x_table_class`. The native hook
profile supports insertion, update and deletion:

```python
from genro_sql import SqlTable


class CustomerTable(SqlTable):
    def trigger_onInserting(self, record):
        record["name"] = record["name"].strip()
        if not record["name"]:
            raise ValueError("Customer name is required")

    def trigger_onInserted(self, record):
        # Returned fields, when requested, are available in this record.
        pass


class ShopWithBehavior(SqlDatabaseConfig):
    def main(self, root):
        customer = root.db("shop", conninfo="dbname=shop").schemas().schema(
            "sales",
        ).tables().table("customer", pkey="id", x_table_class=CustomerTable)
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T")
```

The input mapping is copied before the before-insert hook. Returned fields are
overlaid before the after-insert hook. Hooks may use other tables on the same
database; those operations participate in the same session. A hook failure marks
the unit of work rollback-only, including a failure before any SQL. Hooks cannot
commit, roll back or close the database during a write.

For updates, override `trigger_onUpdating(record, old_record=None)` and/or
`trigger_onUpdated(record, old_record=None)`. For physical deletion, override
`trigger_onDeleting(record)` and/or `trigger_onDeleted(record)`.

When an update or delete hook is overridden, the table first reads and locks the
matching record with PostgreSQL `FOR UPDATE OF` the base table. A declared primary
key and exactly one matching row are required; missing or multiple matches raise
`RecordNotFoundError` or `RecordMultipleRowsError` before any hook runs. Locks last
until commit or rollback. Without overridden hooks, explicit predicates retain
the existing set-based update/delete behavior.

The update before-hook receives the complete physical row overlaid with the
caller's changes. It may modify that record. Both update hooks receive independent
copies of the original locked row as `old_record`. SQL targets the saved old key,
so changing a key in the new record does not redirect the update. Delete hooks
share the loaded record, but changing its key cannot redirect deletion either.
Returned physical fields are mapped back by column identity before the update
after-hook; returning aliases do not rename record fields.

Draft and logical-deletion read filters do not hide the row being written;
partition restrictions still apply. `soft_delete()` and `restore()` follow the
update hook lifecycle. An unexpected affected-row count makes the unit of work
rollback-only, as does any hook error. Related SQL writes share this rollback;
external side effects, such as sending messages, cannot be undone by it.

This native extension mechanism does not load legacy package mixins or implement
field triggers, protection callbacks, counters, related-record cascades or the
full legacy trigger/selection system.

## Ownership and advanced integration

A database and its session belong to their constructing thread. Create separate
database objects for independent contexts. Repeated table lookup within one
instance preserves identity; separate builds have separate live objects and
sessions. Treat configuration as fixed after construction: editing its tree does
not rebuild the resolved model or change an existing session's connection settings.

`SqlBuilder`, `resolve_model`, `QueryCompiler` and the low-level `Database` remain
available independently. `SqlDatabase` binds those responsibilities for application
use; it does not require a second compiler or an alternative migration system.
