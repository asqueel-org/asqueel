# CLI, named configurations and Python console

For this source checkout, install `python -m pip install -e ".[postgresql,migration]"`
from the repository root for the complete PostgreSQL path. The CLI is new in
this checkout; an older PyPI release may not contain it. The
installed `asqueel` command and `python -m asqueel` share one entry point.

Follow the [two-schema walkthrough](two-schemas.md) for the complete configuration,
migration and data-access example.

## Register a configuration folder

A folder contains `configure.py`, defining one `SqlDatabaseConfig` subclass.
Use the standard Builders file-recipe convention: absolute Python imports.
Python package roots containing the recipe are made importable while loading;
other dependencies must already be installed/importable. Module-relative
imports inside schema/table modules work normally.

From the repository root, the two-schema example can be registered as:

```sh
asqueel register gestionale ./examples/two_schemas
asqueel list
asqueel check gestionale
```

The registration is stored at `~/.asqueel/databases/gestionale.json`:

```json
{"folder": "/absolute/path/to/examples/two_schemas"}
```

This follows Kajenn's local named-configuration card convention. The card holds
only the absolute folder path; configuration and credentials are not copied.
`ASQUEEL_HOME` relocates the registry, including for tests. Registration refuses
to replace an existing name. `asqueel unregister gestionale` removes only the
card, leaving project files and the physical database untouched.

The symbolic name identifies a configuration folder. The physical database name
is independently declared by `connection.name` in that configuration.

## Connection declaration

```python
from genro_bag.resolvers import EnvResolver
from asqueel import SqlDatabaseConfig


class Configuration(SqlDatabaseConfig):
    def main(self, root):
        db = root.db()
        db.connection(
            name=EnvResolver("PGDATABASE", default="gestionale"),
            implementation="postgresql",
            host=EnvResolver("PGHOST", default="localhost"),
            port=EnvResolver("PGPORT", default=5432, dtype="L"),
            user=EnvResolver("PGUSER"),
            password=EnvResolver("PGPASSWORD"),
        )
        # Declare schemas/tables here, or call explicitly imported contributors.
```

`connection` is a singleton grammar node, not a named connection registry.
`name` is the physical database name; there is no additional `dbname` field.
The current builder syntax creates the DB node with `root.db()` and then calls
`db.connection(...)`. Each connection attribute is read by `ConfigHandler`,
which resolves `EnvResolver` using its existing standard behavior. A missing
password is omitted, allowing the PostgreSQL driver's normal authentication.
Driver-specific literal options such as `connect_timeout` can use `options`;
reserved connection fields belong directly on the node, and nested resolvers
inside that dictionary are not supported.

Existing root-level `conninfo` / `connect_kwargs` recipes remain supported.
Do not mix these with a `connection` node. The root's old `implementation`
setting belongs to the old form; with a `connection` node, use
`connection.implementation`. The CLI and application share the same connection
settings reader. Named runtime connections, if used, connect to this same physical
DB with these settings; they are not additional configuration entries.

## Inspect and apply migrations

```sh
asqueel db plan gestionale
asqueel db apply gestionale
asqueel db plan gestionale
```

`check` constructs and validates the model and connection settings without
connecting. `db plan` introspects the selected database and prints migration
SQL without applying it. `db apply` prepares a fresh plan, executes it, prints
it, then runs a fresh comparison. It does not replay a previously saved plan.
Both commands use `AsqueelDb.migration_plan()` and `AsqueelDb.migrate()`, the
same methods an application calls from Python (see [migrations](migrations.md)).
`db apply` refuses before any DDL when the backend cannot apply a change, for
example a column type change on SQLite, and names the skipped changes.
The existing `asqueel-migration` PostgreSQL adapter creates a missing database
using its maintenance connection; the configured account needs the appropriate
privileges. The physical target comes from the connection declaration, even
when it differs from the registry name or the recipe root name.

Only the physical schemas represented by the projected tables are managed.
Declare exclusive ownership of those schemas; unrelated objects inside them
can otherwise become removal candidates. Removals are disabled by default;
`--allow-removals` enables them for either `plan` or `apply`. Other alterations
can still affect existing data. A clean result means no remaining commands
under the selected removal policy and migrator capabilities, not equality
including ignored removals. In the current migrator, removal handlers emit
column drops; whole-table, index, relation and constraint removals are no-ops
even with `--allow-removals`. The CLI preserves those existing semantics.
An empty managed table set is rejected by migration commands.

Exit status is zero on success, one on operation failure, skipped changes or
remaining migration commands, two for command syntax errors, and 130 for interruption. Failed DDL
can leave a separately created database behind; the CLI reports the migrator's
rollback/partial-state flags when available. Arbitrary configuration/driver
exception text is not echoed, because it can contain resolved credentials.

These CLI database commands support PostgreSQL and SQLite.
The migrator also has MySQL and SQL Server adapters.
The SQLite runtime and CLI are available; see the [SQLite guide](sqlite.md) for
file layout, locking and migration limitations. MySQL/SQL Server execution remains separate work.

## Python console and ordinary Python

```sh
asqueel shell gestionale
```

The standard Python console starts with `db` available:

```python
rows = db.table("sales.customer").query().fetch()
db.table("sales.customer").insert({"id": 100, "name": "Ada"})
db.commit()
```

Use `db.rollback()` to discard pending changes or recover after a failed domain
operation. Leaving the console, including `exit()`/EOF, closes the database and
rolls back uncommitted work. It never commits implicitly on exit. Console code
has normal Python access to the database object and its configuration; no
persistent console history file is installed by this command.

The same symbolic name works in an ordinary Python terminal:

```python
from asqueel import AsqueelDb

db = AsqueelDb("gestionale")
rows = db.table("sales.customer").query().fetch()
db.close()
```

Call `db.close()` when finished; it rolls back pending work. This constructor
loads the SQL configuration directly; it does not instantiate a Genropy
application or load GUI/services.

## Other configuration sources

Commands accepting a target also accept a folder, a recipe file or a Python
`module:Class`. Use `./folder` for a relative folder, since a bare name always
means a registry entry. Omitting the target uses the current folder's
`configure.py`. `--config SOURCE` is an alternative to the positional target.

```sh
asqueel check --config ./examples/two_schemas/configure.py
asqueel check --config examples.two_schemas.configure:DatabaseConfiguration
```

The same source forms are accepted by `AsqueelDb`, alongside existing
recipe classes, instances and parent configuration layers.
