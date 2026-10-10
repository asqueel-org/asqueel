# Extend configuration with cascading grammars

For most applications, compose `SqlDatabaseConfig` recipes with helper functions
and parent layers. Change the grammar only when a schema or table needs its own
validated vocabulary or defaults. This is an advanced extension of the same
configuration-to-object path, not a second model mechanism.

## Separate layering from grammar selection

**Layers** supply values at matching configuration paths: a deployment can replace
a connection string while retaining application tables. **Mounted grammars**
change which declarations, parameters and signature defaults are valid below a
node. A schema grammar can choose a table grammar, which in turn defines columns.

The effective configuration read stack sees explicit values before grammar
signature defaults and a caller-provided fallback. Rendering resolves those
defaults into the model as well; they are not only display-time defaults.

## A complete offline example

This example narrows the column declaration for demonstration: omitted column
dtypes default to `I`, and `ui_hint` is an additional descriptive attribute. It
does not include every option of the standard column grammar.

```python
from genro_builders.builder import element
from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.elements import ColumnElements, SchemaElements, TableElements


class AppColumns(TableElements, ColumnElements):
    @element(parent_tags='columns', _meta={'projects_column': True})
    def column(self, name: str, dtype: str = 'I', ui_hint: str = 'Number'):
        ...


class TableConfig:
    grammar = AppColumns


class AppSchema(SchemaElements):
    @element(parent_tags='tables', _meta={'subbuilder': 'x_config:grammar'})
    def table(self, name: str, pkey: str | None = None, x_config=None, **extra):
        ...


class SchemaConfig:
    grammar = AppSchema


class App(SqlDatabaseConfig):
    @element(parent_tags='schemas', _meta={'subbuilder': 'x_config:grammar'})
    def schema(self, name: str, x_config=None, **extra):
        ...

    def main(self, root):
        schema = root.db('example').schemas().schema(
            name='sales', x_config=SchemaConfig,
        )
        table = schema.tables().table(
            name='customer', pkey='id', x_config=TableConfig,
        )
        columns = table.columns()
        columns.column(name='id', ui_hint='Identifier')
        columns.column(name='rank')


db = AsqueelDb(App)
try:
    rank = db.table('sales.customer').column('rank')
    assert rank.config('dtype') == 'I'
    assert rank.model.dtype == 'I'
    assert rank.config('ui_hint') == 'Number'
    assert db.table('customer').column('id').config('ui_hint') == 'Identifier'
finally:
    db.close()

```

The schema mount selects `SchemaConfig.grammar`. Its table declaration selects
`TableConfig.grammar`. The column's `projects_column` metadata tells SQL model
resolution that it describes a column. `AsqueelDb()` follows the same
rendering process as a standard recipe and performs no database I/O.

Use the supported SQL element tags and retain relevant projection metadata when
customizing declarations. Adding a new grammar element does not automatically
teach the SQL model, compiler or migration bridge to execute it.

## Mount Asqueel in a host configuration

Another configuration dialect — an application server, for example — can let
its users declare Asqueel databases inside its own configuration. The host
mounts `AsqueelDb.grammar` on one of its elements and builds each database with
`AsqueelDb(node)` from the resulting `db` node.

The host declares the mount point with a subbuilder reference to the grammar
its `db_class` carries:

```python
from genro_builders.builder import element
from genro_builders.contrib.config import ConfigBuilder


class HostElements:
    @element(sub_tags="databases[0:1]", node_label="configuration")
    def configuration(self): ...

    @element(parent_tags="configuration", sub_tags="database", collection_key="code")
    def databases(self): ...

    @element(parent_tags="databases", _meta={"subbuilder": "db_class:grammar"})
    def database(self, db_class: type, code: str | None = None): ...


class Host(HostElements, ConfigBuilder):
    pass
```

Keep the database model in a function that receives a `db` node. The host calls
it under its own element, starting from `db()`; a standalone recipe calls the
same function, so the CLI can plan and apply migrations without a second copy
of the model:

```python
from asqueel import AsqueelDb, SqlDatabaseConfig


def chat_archive(db):
    db.connection(name="/srv/data/chat.db", implementation="sqlite")
    columns = db.schemas().schema("chat").tables().table("message", pkey="id").columns()
    columns.column("id", dtype="L")
    columns.column("text", dtype="T")


class Configuration(Host):
    def main(self, root):
        database = root.configuration().databases().database(db_class=AsqueelDb, code="alfadb")
        chat_archive(database.db())


class ChatArchive(SqlDatabaseConfig):  # standalone recipe for the CLI
    def main(self, root):
        chat_archive(root.db())
```

The host builds the database from the `db` node of its configuration:

```python
from genro_builders.contrib.config import ConfigHandler

config = ConfigHandler(Configuration)
db = AsqueelDb(config.builder.source.get_node("configuration.databases.alfadb.db"))
```

`AsqueelDb(node)` replays the subtree into a recipe, element by element, so the
model and connection settings are the same as `AsqueelDb(ChatArchive)` gives.
The SQL naming rules apply in the host as in a recipe: one `db` per mount point,
no duplicate names in the same namespace. A node other than `db` is refused.

## Boundaries of customization

- The effective model is built from a private copy; resolving defaults does not
  rewrite the authored recipe.
- Keep grammar classes explicit and verify both `.config` and `.model` when
  composing declaration rules.
- A generated Python recipe is not a round trip of arbitrary dynamic grammar
  mounts, class hierarchy or original file decomposition.
- Custom attributes describe the application; they do not automatically add UI
  rendering, query options or database types.

Use the [generated grammar reference](../grammar.md) to inspect the standard
vocabulary, and [configuration](configuration.md) for ordinary value layering.
