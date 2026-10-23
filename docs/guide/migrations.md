# Project and migrate a physical schema

Query execution and schema migration are separate operations. Asqueel builds
a physical description; `asqueel-migration` compares that description with a
database and prepares migration commands.

Install the migration dependency, plus the PostgreSQL one for PostgreSQL databases:

```sh
pip install 'asqueel[migration]'              # SQLite
pip install 'asqueel[postgresql,migration]'   # PostgreSQL
```

## Migrate from Python

An application creates and evolves its tables from its `AsqueelDb`, on SQLite
and PostgreSQL, with two methods:

```python
from asqueel import AsqueelDb, MigrationError

db = AsqueelDb(ChatArchive)

plan = db.migration_plan()       # compares the model with the live database; changes nothing
print(plan['sql'])               # the DDL that migrate() would run
print(plan['warnings'])          # backend warnings, including skipped changes
print(plan['skipped'])           # changes the backend cannot apply

db.migrate()                     # applies the plan and returns the result
```

The plan is the dict of `asqueel_migration.plan_migration()`; the result of
`migrate()` is the dict of `asqueel_migration.apply_migration()`, with the same
keys plus `execution`, `backups`, `verified` and `remaining`.

`migrate()` refuses before running any DDL when `plan['skipped']` is not empty,
for example a column type change on SQLite. After applying, it compares the
model with the database again and raises `MigrationError` if differences remain.
On an up-to-date database `plan['empty']` is true.

Both methods work for every way of building an `AsqueelDb`, including a database
declared in a host configuration (`AsqueelDb(node)`, see
[cascading grammars](configuration-grammars.md)). The database name comes from
the connection settings; a missing PostgreSQL database is created. A SQLite
`:memory:` database is migrated through the application's existing connection,
including introspection and the comparison after applying the migration.

`allow_removals=True` enables the supported removals, currently columns only.

Three more options come from the GenroPy migration, with the same keywords on
both methods:

- `foreignKeys=False` creates no foreign key constraint. The indexes of the
  relation columns stay. Foreign keys already in the database are kept: the
  migration does not remove relations.
- `force=True` converts a filled column to a new type. Values that do not
  convert become NULL. Without it, such a conversion raises `MigrationError`.
- `backup=True` implies `force` and first copies the column into
  `<column>__<old dtype>`. After applying, a backup column without lost values
  is dropped; a kept one adds a warning to the returned result.

```python
result = db.migrate(backup=True)
for warning in result['warnings']:
    print(warning)   # app.event.happened: 1 value(s) not converted, kept in backup column happened__T
```

### Indexes the model implies

The migration creates, as GenroPy:

- an index on the columns of every relation declared on a physical column or a
  `compositeColumn`, with or without `foreign_key`, unless the relation says
  `indexed=False`;
- an index on the target columns of a relation whose target is not the target
  pkey;
- an index for `column(indexed=True)` or `column(indexed={...})`.

Pkey columns and unique columns get no index. `indexed={...}` carries the index
options: `method`, `where`, `tablespace`, `sorting` (comma-separated, one
direction per column), `with_<name>` (a `WITH` storage option) and `unique`.
`unique` without `where` makes the column unique and creates no index; with
`where` it is a partial unique index. Any other key raises.

```python
columns.column('code', dtype='T', indexed=dict(where='code IS NOT NULL', sorting='DESC',
                                               with_fillfactor=70))
```

The [CLI](cli.md) provides `asqueel db plan NAME` and `asqueel db apply NAME`
on top of the same methods. The lower-level API below remains available.

## Experiment in a Python console, without files

Start Python in an environment containing `asqueel[migration]`. Declare a
builder directly; no configuration file or recipe subclass is required:

```python
from asqueel import AsqueelDb, SqlDatabaseConfig

model = SqlDatabaseConfig()
root = model.source.db(implementation="sqlite")
root.connection(name=":memory:", implementation="sqlite")
product = root.packages().package("shop", sqlschema="shop").table("product", pkey="code")
product.column("code", size=":10")
product.column("name", size=":60")

db = AsqueelDb(model)
print(db.migrate()['sql'])
products = db.table("shop.product")
products.insert({"code": "TEA", "name": "Tea"})
db.commit()
products.query(columns="$code, $name").fetch()
products.update({"name": "Green tea"}, pkey="TEA")
db.commit()
```

The builder and the running model are separate snapshots. Add columns to the
builder, explicitly reload the model, then migrate the same database:

```python
product.column("category", size=":30")
product.column("stock", dtype="I")
db.reloadModel(model)
print(db.migrate()['sql'])

products = db.table("shop.product")  # Fresh handle for the new model.
products.update({"category": "Drinks", "stock": 8}, pkey="TEA")
db.commit()
products.query(columns="$name, $stock").fetch()
db.commit()
```

Even the CSV can be held in memory for a short demonstration:

```python
import csv
from io import StringIO

data = StringIO("code,name,category,stock\nCOF,Coffee,Drinks,24\nMUG,Mug,Kitchen,12\n")
for row in csv.DictReader(data):
    row["stock"] = int(row["stock"])
    products.insert(row)
db.commit()
products.query(
    columns="$name, $stock",
    where="$category = :category", category="Drinks",
    order_by="$stock DESC",
).fetch()
# [[name=Coffee,stock=24], [name=Green tea,stock=8]]

db.closeConnection()  # Discards this in-memory database.
```

The in-memory path borrows the main SQLite connection. It never closes it
during planning, applying or verifying a migration. Attached SQL schemas are
also in memory. There are no database files to persist between processes:
exiting Python, closing the connection, or constructing a different `AsqueelDb`
creates a different database.

`reloadModel(source, parents=None)` is for an exclusively
used, single-threaded SQLite `:memory:` session with only the main connection
open. It validates the replacement
before swapping models, keeps the connection, and refuses changes to connection
settings or SQL schemas. It changes the model only; `migrate()` applies the DDL.
Obtain fresh table and query handles after reloading: old handles are invalid.
The original builder is not watched for changes.

A relation added to a table that already exists needs
`migrate(foreignKeys=False)`: SQLite cannot add a foreign key to an existing
table, so the migration creates the column and its index without the
constraint. The relation works in queries (`@category_code.name`) because
joins come from the model.

Both in-memory migration methods and model reload require an idle session.
Commit or roll back pending work first, including after reads, and finish any
deferred callbacks. They refuse unfinished work rather than committing or
discarding it. A failed DDL transaction is rolled back without closing the
database. File-backed SQLite and PostgreSQL retain their existing migration
paths.

The complete executable example is
[`examples/sqlite_memory.py`](../../examples/sqlite_memory.py).

(native-package-models)=
## Native package models

The migration renderer prepares the source as the live model does: options
that add columns are expanded once and package rules apply. Render the composed
recipe of the database:

```python
from asqueel import AsqueelDb
from examples.test_invoice_pg import source

db = AsqueelDb(source())
try:
    migration_data = db.config.builder.render(mode='migration')
finally:
    db.closeConnection()
```

This example requires the repository checkout. To write the JSON artifacts,
run `PYTHONPATH=.:src python scripts/export_invoice_migration.py` from its root,
with the migration extra installed. The script writes
`artifacts/test_invoice_pg/native/migration.json`; it does not connect to a database.

The native corpus covers 74 tables in sys, adm and invc. Its JSON is checked
against an independent legacy oracle, excluding the agreed `sys.locked_record`.
A dedicated PostgreSQL test applies this structure, introspects it and verifies
an empty second diff, including after controlled changes to columns, constraints
and indexes. Application data migration and package formula execution are outside
this verification.

## Physical names in migration data

`recipe.render(mode='migration')` renders the source under its physical names:
the schema (`sqlschema`, or the default schema of the implementation for a
package), the table prefix (`sqlprefix`), and the explicit `sqlname` of schemas,
tables and columns. These are the names used by the query compiler.
`foreignKeys=False` renders no foreign key; the relation indexes stay. A path,
a writable or a callable passed as `target` receives the structure as JSON text.

The result is normalized migration data, not SQL. It contains physical columns,
keys, supported constraints and indexes. UI metadata, formula columns, identities
used by the application and row policies are excluded from physical DDL. Retain
the original application model alongside this structure.

## Prepare commands for an existing database

`AsqueelDb.migration_plan()` and `migrate()` cover the usual case. The function
below shows the same steps with the `asqueel-migration` objects, for PostgreSQL.
It inspects only the physical schemas selected by the model and returns the
migrator and its prepared command text:

```python
from psycopg.conninfo import conninfo_to_dict
from asqueel_migration import PgDatabase, SqlMigrator


def prepare_migration(dsn, db):
    model = db.model
    desired = db.config.builder.render(mode='migration')
    params = conninfo_to_dict(dsn)
    # The database to create or migrate is the DSN one, not the recipe root label.
    desired['root']['entity_name'] = params['dbname']
    schemas = sorted({table.physical_schema for table in model.tables.values()})
    if not schemas:
        raise ValueError('Choose a nonempty application schema to migrate')
    database = PgDatabase(params, application_schemas=schemas)
    migrator = SqlMigrator(
        database,
        ignore_constraint_name=True,
        removeDisabled=True,
    )
    migrator.ormStructure = desired
    migrator.prepareMigrationCommands()
    return migrator, migrator.getChanges()
```

Include an explicit `dbname` in the DSN; `PgDatabase` requires it. The migrator's
application-schema list must be the schemas you intend to manage. A schema
shared with unrelated application objects needs a deliberate ownership strategy.

`removeDisabled=True` suppresses removal events; it does not guarantee that all
other changes are harmless or reversible. Inspect the returned commands for the
actual change you intend. To apply the prepared commands, call
`migrator.applyChanges()` explicitly. After applying, prepare a fresh migration
from the same desired model and check that `getChanges()` is empty. Do not infer
idempotence merely from successful execution.

## Handle rejected structures

The migration renderer raises `UnsupportedFeatureError` when it cannot safely
represent the source: for example a partial index or a CHECK constraint on a
table whose columns are renamed by `sqlname`. Diagnostics identify objects
requiring a richer representation or separate migration ownership.

Do not delete preserved metadata simply to make the rendering
succeed. Resolve the unsupported feature or manage that schema through a tool
that represents it.

In native declarations, every
relation on a physical column requests an index on its columns, with or without
`foreign_key`; declare `indexed=False` on the relation when that is not intended.

## Read or export migration recipes

`SqlModelReader` accepts normalized migration data, not a database connection:

```python
from asqueel import SqlModelReader


def recipe_source(normalized_structure):
    builder = SqlModelReader(normalized_structure).to_builder()
    return builder.render(mode='python', class_name='ImportedDatabase')
```

The returned source is a Python `SqlBuilder` recipe you can save and maintain.
Unsupported structure fields are reported as errors rather than silently
omitted. The migration structure does not contain UI overlays, query formulas
or row-policy configuration; this round trip cannot reconstruct them.

See [Models](models.md) for application declarations.

## PostgreSQL serial key widths

`dtype="serial"` retains its existing 64-bit BIGSERIAL meaning. The additive
`dtype="serial4"` declaration requests a 32-bit PostgreSQL SERIAL key. Native
migration requires `asqueel-migration>=0.3.5`, required by the core's
`migration` and `dev` extras. Published migration 0.2.2 includes `serial4` support.

With the updated migration engine, a populated SERIAL4 column declared as
`serial4` produces no DDL and retains its sequence/default. Declaring it as `I`
also preserves the existing column, but an `I` declaration on a fresh database
does not request a sequence. Changing to the 64-bit `serial` declaration is a
separate explicit migration, tracked in
[asqueel-migration #27](https://github.com/asqueel-org/asqueel-migration/issues/27).


asqueel-migration introspects generated columns: on SQLite through
`table_xinfo`, including in-memory databases, on PostgreSQL through
`information_schema.columns`. Changes to an existing generated expression are reported
as skipped work, so the plan is not empty and `migrate()` refuses before DDL.
Apply an explicit migration for these changes. PostgreSQL compares the actual
catalog expression with the model through planner normalization.
