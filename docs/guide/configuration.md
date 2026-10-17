# Configuration and application objects

`SqlDatabaseConfig` declares connection settings and a SQL model in the same
Builders recipe. `AsqueelDb()` produces a synchronous `SqlDatabase` with
stable table, column and relation objects. Construction validates and binds the
model without connecting, executing SQL, or applying migrations.

The [CLI and named configurations](cli.md) guide covers named
`connection` declarations with `EnvResolver`, `~/.asqueel` registration,
migration commands and a Python console with `db` available. The older root
connection attributes shown below remain supported.

`AsqueelDb("gestionale")` loads a registered configuration and returns a
persistent database object. Use `db.commit()`, `db.rollback()` and `db.close()`
explicitly. The previous `build_database(...)` function remains available as a
compatibility factory returning an `AsqueelDb` instance.

## Construct a database or render a recipe

```python
from asqueel import SqlDatabaseConfig, AsqueelDb


class Shop(SqlDatabaseConfig):
    def main(self, root):
        database = root.db("shop", implementation="postgres", conninfo="dbname=shop")
        table = database.schemas().schema("sales").tables().table(
            "customer", pkey="id", name_long="Customers",
        )
        columns = table.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", x_ui_label='Name')


db = AsqueelDb(Shop)
assert db.table("sales.customer").model is db.model.table("sales.customer")
assert db.table("sales.customer").attributes["name_long"] == "Customers"
db.close()

recipe = Shop()
recipe.create()
db = recipe.render()
print(db.table("sales.customer").query(columns="$id, $name").sqltext)
db.close()
```

The default renderer is an object renderer. `render()` returns a database, not
DDL or serialized configuration. Structural changes belong to the migration integration.

The root declares `name`, `implementation='sqlite'`, `conninfo=''`, and
optional `connect_kwargs`. An empty connection string uses the driver's normal
connection defaults when an operation is eventually executed. The
implementations are `sqlite` (see [SQLite](sqlite.md)), `postgres` and
`postgres3`, as in GenroPy; `<name>:<module>` loads the adapter of another
module (see [Adapters](adapters.md)). `connect_kwargs={'autocommit': True}` is rejected.

`AsqueelDb(source, *, parents=None, environment=None)` accepts a recipe class, an existing builder instance, or a
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
        root.db("shop", implementation="postgres", conninfo="host=localhost dbname=shop_test")


db = AsqueelDb(Deployment, parents=[Shop])
try:
    assert db.config("conninfo") == "host=localhost dbname=shop_test"
    assert db.table("sales.customer").config("pkey") == "id"
finally:
    db.close()

```

Configuration reads use the handler's read stack: written values, annotated
signature defaults, then the caller's explicit default. A missing value without
a default raises `KeyError`. Explicit nullable SQL attributes retain `None`;
`False`, zero and empty strings also remain values.

```python
db = AsqueelDb(Shop)
try:
    assert db.config("implementation") == "postgres"
    customer = db.table("sales.customer")
    assert customer.config("pkey") == "id"
    assert customer.column("name").config("dtype") == "T"
    assert customer.config("optional_hint", default=False) is False
finally:
    db.close()

```

`db.config` is the single global handler. Table and column views delegate to it
using their declaration paths. For example, `customer.config('pkey')` reads
`schemas.sales.tables.customer.pkey`. These views do not maintain independent
copies of configuration attributes.

Alias-column configuration views additionally fall back to their target column
for missing values. The alias's `model` retains resolved metadata and its own
identity; `originalColumn` links to the live target. See [alias columns](models.md).

Defaults from the effective grammar are resolved on a separate source copy before
building the semantic model. A mounted column grammar's default dtype therefore
also reaches `.model.dtype`; it is not merely a display-time configuration value.
The authored configuration remains unchanged. Compose SQL declarations and
schema/table grammar mounts to define the effective application vocabulary.

For a complete schema-to-table grammar mount, see
[cascading configuration grammars](configuration-grammars.md). Value layering
and grammar selection are separate choices.

## Read and write through a table

Against an existing database with the example table:

```python
db = AsqueelDb(Shop)
try:
    customer = db.table("sales.customer")
    try:
        customer.insert({"id": 1, "name": "Ada"})
        rows = customer.query(where="$id = :wanted", wanted=1).fetch()
        assert rows[0]["name"] == "Ada"
        db.commit()
    except Exception:
        db.rollback()
        raise

finally:
    db.close()

```

`query()` creates detached query intent; `.sqltext` compiles it, and `.fetch()`
executes it. Parameters are keyword arguments such as `minimum=100`; `sqlparams={...}`
takes a mapping when names are built at runtime or clash with an option. Unused keyword
arguments fail rather than silently turning a misspelled option into a parameter.
Queries compile in the environment current at the terminal call.

`record(pkey)` returns a lazy exactly-one reader. `.output('dict')` returns a
copy of its cached result; `.refresh()` reloads it in the current environment.
`record(pkey, mode='dict')` is the immediate form. `output('record')` returns a Bag without relation resolvers. `ignoreMissing=True`
returns an empty result. `query.count()` follows the legacy count algorithm;
Selection remains outside this profile.

Insert, update, delete, soft-delete and restore return `QueryResult`. Read the
[transaction guide](transactions.md) before using writes: operations share the selected connection and do not commit individually.

## Add business behavior

Configure `x_table_class=YourTableSubclass` to attach before/after insert, update
and deletion hooks. See [table hooks](hooks.md) for the complete example, locking
semantics and transaction rules.

## Ownership and advanced integration

A database shares its model and table handles between threads. Connections and
mutable execution state are isolated per thread. Repeated table lookup within one
instance preserves identity; custom table classes must not store per-request state
on shared attributes. Table and column nodes expose the completed model through `.attributes`;
editing the source or `db.config.builder` does not alter their structural values.
`db.config` retains administrative connection configuration. Editing it does not
reconfigure an already-open physical connection.

`SqlBuilder`, `resolve_model`, `QueryCompiler` and the low-level `Database` remain
available independently. `SqlDatabase` binds those responsibilities for application
use; it does not require a second compiler or an alternative migration system.

### Connection implementation inheritance

`connection(implementation=...)` selects the backend; when omitted it inherits
`db(implementation=...)`, whose default is PostgreSQL. Named connections use the
same dialect as the DB root:

```python
root.db("demo", implementation="sqlite").connection("main", database="app.db")
```

Use `database` for the physical database and `name` for the logical connection.
Additional connections may target other databases of the same dialect. Select
one through `db.tempEnv(connectionName="reporting")`; `main` must be declared.
For PostgreSQL, `dsn` is an alternative to the individual connection fields.
Driver options belong to `connection.options().driver(...)`.

For compatibility, declarations without `database` or `dsn` still interpret
`name` as the physical database name and allow an explicit connection backend
to override the root default. The [CLI guide](cli.md) distinguishes these older
forms from named connections and documents resolver handling.
