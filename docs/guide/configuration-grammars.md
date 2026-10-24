# Extend configuration with cascading grammars

For most applications, compose `SqlDatabaseConfig` recipes with helper functions
and parent layers. This is an advanced extension of the same
configuration-to-object path, not a second model mechanism.

## Separate layering from grammar selection

**Layers** supply values at matching configuration paths: a deployment can replace
a connection string while retaining application tables. **Mounted grammars**
change which declarations, parameters and signature defaults are valid below a
node.

The effective configuration read stack sees explicit values before grammar
signature defaults and a caller-provided fallback. Rendering resolves those
defaults into the model as well; they are not only display-time defaults.

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
    columns = db.packages().package("chat", sqlschema="chat", sqlprefix=False).tables().table("message", pkey="id").columns()
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

## Own databases in a server and its applications

A host — a server and its applications — mixes in `AsqueelDbMixin` to own
Asqueel databases by name and hand them to each call. The host defines two
members: `asqueel_owner_name` (`''` for the server, the application code for an
application) and `asqueel_owner(name)` (the owner with that name, `''` for the
server).

```python
from asqueel import AsqueelDbMixin


class Server(AsqueelDbMixin):
    def __init__(self):
        super().__init__()
        self.applications = {}

    @property
    def asqueel_owner_name(self):
        return ''

    def asqueel_owner(self, name):
        return self if name == '' else self.applications[name]


class App(AsqueelDbMixin):
    def __init__(self, server, code):
        super().__init__()
        self.server, self.code = server, code
        server.applications[code] = self

    @property
    def asqueel_owner_name(self):
        return self.code

    def asqueel_owner(self, name):
        return self.server.asqueel_owner(name)
```

Each owner registers its databases with `set_asqueel_db(name, source)`, where
`source` is anything `AsqueelDb` accepts, including a mounted `db` node. A call
then takes them:

| Expression | Database |
|---|---|
| `app.db` | the application's `default`, or the server's when the application has none |
| `app.get_db("betadb")` | the server's `betadb` |
| `app.get_db("chat:alfadb")` | the `alfadb` of application `chat` |

The first take of a database during a call enters
[`session(db)`](transactions.md#sessions) on it. The session clears
`currentEnv`, so a call never sees the context left by the previous call on
that thread. A database already in a session on the thread, taken through
another owner, is used as it is. At the end of the call, on the same thread,
the host calls `release_databases()` on the owner the call used: it leaves the
sessions opened through that owner, which rolls back what was not committed
and closes the connections, and the next take starts a new call. One call runs
on one thread; each thread releases only its own takes.

## Boundaries of customization

- The effective model is built from a private copy; resolving defaults does not
  rewrite the authored recipe.
- A generated Python recipe is not a round trip of arbitrary dynamic grammar
  mounts, class hierarchy or original file decomposition.
- Custom attributes describe the application; they do not automatically add UI
  rendering, query options or database types.

Use the [generated grammar reference](../grammar.md) to inspect the standard
vocabulary, and [configuration](configuration.md) for ordinary value layering.
