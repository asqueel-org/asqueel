# Release notes

## Unreleased

- Require `asqueel-migration>=0.3.5`. Its reader introspects generated columns
  on SQLite and PostgreSQL and borrows a SQLite `:memory:` connection; its
  service plans and applies the migration with `force`, `backup` and the backup
  report.
- `db.migration_plan()` returns the dict of `asqueel_migration.plan_migration()`
  (`sql`, `warnings`, `skipped`, `empty`, ...); `db.migrate()` returns the dict of
  `asqueel_migration.apply_migration()`. The `MigrationPlan` class is removed:
  `plan.commands` becomes `plan['sql']`, `plan.empty` becomes `plan['empty']`.
- Remove the internal copies of those features: the modules
  `asqueel.sqlite_migration`, `asqueel.generated_migration` and
  `asqueel._memory_migration`.

## 0.7.0 — Consolidation and unified model candidate

- Use the hierarchical `DbModel` for authored models, SELECT/write compilation
  and physical migration projection.
- Remove the disconnected `ResolvedModel`, `Column`, `Table` and `Relation`
  descriptors and their separate migration projection.
- Remove the catalog import (`inspect_postgres`, `CatalogProvider`) and the model
  JSON codec (`model_to_json`, `model_from_json`). Reading a model from a database
  belongs to asqueel-migration; the recipe source will be saved as TYTX.
- No query features or optimizations are added in this release.
- Preserve parameter-like text inside SQL strings, quoted identifiers and comments,
  including scoped formula bindings and environment parameters (#35).
- Cover PostgreSQL dollar/E strings, nested comments, SQLite quoting, adjacent
  parameters and collection expansion with regression and live database tests.
- Correct the alias handle, zero limit, missing environment value and SQL/application
  cascade documentation (#27, #37).
- `read_only` is spelled `readOnly`, as in GenroPy.
- One object renderer, mode `objects`, declared on `SqlBuilder` and reached only
  through `AsqueelDb(source)`, which renders the composed recipe into the
  database (`recipe.render(target=db)`); `recipe.render()` without a database
  raises `TypeError`. Removed: `build_database` (use `AsqueelDb`),
  `resolve_model` (use `AsqueelDb(source).model`), the `objects_tree` mode and
  `renderer_objects_tree`, `SqlRenderer` and `renderer_sql`, the modules
  `asqueel.model`, `asqueel.renderer` and `asqueel.object_renderer`, and the
  `objects_tree` migration artifact and its export script.
- The migration structure is rendered from the source by `SqlMigrationRenderer`,
  a genro-builders renderer declared as `renderer_migration` on `SqlBuilder`:
  `recipe.render(mode='migration', foreignKeys=True)`. `sqlname` on schemas,
  tables and columns is always applied. Removed: `to_physical_builder` and the
  modules `asqueel.projection` and `asqueel.object_tree_projection`;
  `SqlMigrationRenderer(builder).render()` becomes `builder.render(mode='migration')`.
- One database class, built before its model as in GenroPy: `AsqueelDb` exists
  first, then the objects renderer builds `DbModel(db)` into it with
  `model.build(fragment)`. `SqlTable(tblobj)` takes the table object only; the
  database is `tblobj.db`. The environment lives on the database:
  `AsqueelDb(source, environment=)` takes a mapping of defaults and
  `db.environment_snapshot()` returns the detached copy. A subclass of `AsqueelDb`
  may declare `main(self, root)` and is then called without a source. Removed:
  `Database` (an `AsqueelDb` over a recipe with no package executes statements),
  `SqlDatabase`, `SqlEnvironment`, `ApplicationEnvironment`, `DbDatabaseObj`,
  `db.environment`, and the environment-type check of `session(db)`.
- The Python recipe is rendered from the source by `SqlPythonEmitter`, a
  genro-builders renderer declared as `renderer_python` on `SqlBuilder`:
  `recipe.render(mode='python', class_name='ImportedDatabase')`. Removed:
  the `SqlPythonEmitter.emit` method.

## 0.6.1

- Execute standalone `auto_counter` and `relative_index` options, column
  defaults and `read_only`/`unmodifiable` checks in the ordinary write cycle.
- Maintain hierarchies with custom parent/counter fields and linked master
  roots; serialize structural changes, reject cycles and refresh paths after
  before-hooks. Preserve cascade rollback and skip descendants already deleted.
- Apply physical `partition_<field>` scopes to insert/update/delete, including
  direct SQL APIs, with an explicit `ignore_partition=True` bypass.
- Introspect SQLite generated columns (including in-memory databases), keep
  generated values out of ordinary UPDATE assignments, and refuse migration
  plans that would silently ignore changed generated expressions.

## 0.6.0

- `onDelete_sql`/`onUpdate_sql` accept the legacy abbreviations `C`, `R`, `N`,
  `SN`, `SD`, in any case.
- Every relation on a physical column indexes its columns, also with
  `foreign_key=False` (`indexed=False` skips it); a relation to target columns
  other than the target pkey also indexes them on the target table. A column
  that is part of the pkey gets no index, as legacy. The first migration after
  the upgrade therefore adds `CREATE INDEX` commands for relations without a
  foreign key, for non-pkey targets and for `indexed={...}` options.
- `indexed={...}` options that differ from an explicit `index()` on the same
  columns raise `UnsupportedFeatureError`; so does a partial or non-btree
  explicit index on a relation target that needs a full one.
- `column(indexed={...})` carries the index options: `unique`, `method`,
  `where`, `tablespace`, `sorting`, `with_<name>`. `unique` without `where`
  makes the column unique instead of creating an index.
- `migration_plan()` and `migrate()` take `foreignKeys`, `force` and `backup`;
  the CLI `db plan|apply` takes `--no-foreign-keys`, `--force`, `--backup`. A
  conversion on a filled column without `force` raises `MigrationError`, and so
  does an error while applying the DDL. With `backup`, a kept backup column
  adds a warning to the returned plan and does not fail the final re-check.
  `SqlMigrationRenderer` takes `foreignKeys`.
- SQLite schema files change name, as in GenroPy: each attached schema is
  `<schema>.db` in the folder of the main file, no longer `<stem>_<schema>.db`.
  An existing SQLite database needs its schema files renamed. A missing main
  file gets its folder created.
- SQLite connection option `foreignKeys` (default `True`): `False` runs
  `PRAGMA foreign_keys = OFF`. PostgreSQL refuses it.
- `vacuum()` on SQLite runs `VACUUM` on every attached schema, not only `main`.
- SQLite DDL declares the legacy type names (`character varying`, `character`,
  `timestamp`, `time`); requires asqueel-migration 0.3.1.
- Connection lifecycle as in GenroPy. `session(db, **env)` is the unit of work
  outside a request: entry clears `currentEnv` and applies `env`, exit calls
  `closeConnection()`, also when the body raises. `closeConnection()` rolls
  back what was not committed and closes every named connection of the
  thread; the database stays usable.
- Removed in favour of `session(db)` and `closeConnection()`: `close()`,
  `with db:` (also `with build_database(...) as db:`), `acquire()`, the
  `outcome` property and the error class raised by a closed database.
- `deferToCommit` and `deferAfterCommit` queues live in `currentEnv`, under the
  GenroPy keys; `clearCurrentEnv()` drops them. `deferredRaise` keeps its
  exceptions in `currentEnv['_pendingExceptions__main_db_<connectionName>']`,
  one list per named connection (GenroPy keeps one global `_pendingExceptions`).
- `AsqueelDbMixin` enters `session(db)` at the first take of a database during
  a call and leaves it in `release_databases()`.

This release completes the structural path from native package configuration to
live model objects and migration JSON. Package schemas follow the legacy rules;
table and column declarations retain labels, captions and the other attributes
their grammar declares; an attribute outside the grammar raises. Existing
Builders resolvers supply external or calculated values.

- Expand structural options, including system fields, hierarchies, counters,
  dynamic fields, audit and attachments, before resolving cross-table relations
  and aliases. Other options remain declarations on the completed model.
- Produce migration data from the completed objects without reading an expanded
  legacy source or repeating option expansion. Normalize logical types at the
  physical projection boundary.
- Include the native `test_invoice_pg` example: 74 tables across sys, adm and
  invc, 789 physical columns, 522 virtual columns, 58 foreign keys and 282 indexes.
  Its migration JSON equals the legacy oracle after excluding `sys.locked_record`.
- Keep `validate_*` as column validations; `validate_values` deliberately replaces
  legacy `values`. `sys_fields(syscode=True)` adds an indexed UNIQUE column
  without reintroducing system records.

System records, locked records, release options and optional diagnostics remain
deferred. Virtual relations retain paths/conditions, `var_*` and `ask`; inverse,
ordering, limits and virtual cardinality are deferred. Rendering these package
declarations does not implement their formula compilation, hooks, validation or
record-write behavior. The existing low-level compiler/runtime keeps its own
supported profile; see [current status](limitations.md).

The published 0.6.0 dependency baseline is `asqueel-migration>=0.3.1,<0.4`,
`genro-bag>=0.28.0,<0.29` and `genro-builders>=0.29.0,<0.30`.
See [native package migrations](migrations.md#native-package-models) for reproduction.

## 0.5.2

- Accept `asqueel-migration>=0.1.2,<0.3`, including the 0.2 series used by
  Asqueel DB Manager. The migration engine remains an optional dependency;
  Asqueel does not require Kajenn or DB Manager to migrate a database.
- Development and CI use the published migration engine 0.2.0 instead of a
  temporary Git revision. Dictionary-based migration inputs remain compatible
  with the engine's independent source snapshots.

Validation: 868 tests passed, 1 skipped, including PostgreSQL integration,
against the coordinated migration engine 0.2.0 wheel.

## 0.5.1

Released on PyPI and tagged `v0.5.1`.

- Migrate from Python. `AsqueelDb.migration_plan()` compares the model with the
  live database and returns a plan (`commands`, `warnings`,
  `skipped`, `empty`) without changing anything; `AsqueelDb.migrate()` applies
  it. `migrate()` refuses before any DDL when the backend cannot apply a change
  (for example a column type change on SQLite) and raises `MigrationError` when
  differences remain afterwards. Both work for a `db` node mounted in a host
  configuration. See "Migrate from Python" in the migrations guide.
- `asqueel db plan/apply` use the same methods. Changed behaviour: `db apply`
  now exits 1, naming the skipped changes, instead of 0 with a warning.
- Databases per call. `AsqueelDb.acquire` took a database for the current
  call: the first take on a thread cleared `currentEnv`, and `closeConnection()`
  ended the take. It was removed later in favour of `session(db)`. `AsqueelDbMixin` gives a server and its applications databases
  by name (`set_asqueel_db`, `db`, `get_db` with `app:db` names) and closes the
  ones taken through an owner (`release_databases`). See "Own databases in a
  server and its applications" in the configuration grammars guide.
- `asqueel-migration` is required as `>=0.1.2,<0.2`.
- The CLI install hint asks for `asqueel[migration]`, and for
  `asqueel[postgresql]` only on PostgreSQL.
- Guides aligned with the code: query bindings, default ordering, relation
  result names, `*` expansion, SQLite support, troubleshooting entries.

Validation: 868 tests passed on PostgreSQL and SQLite, with 95% coverage.
Ruff, mypy and the strict documentation build passed.

## 0.5.0

Released on PyPI and tagged `v0.5.0`.

- A host configuration can declare Asqueel databases in place. `AsqueelDb.grammar`
  is `SqlDatabaseConfig`: a host mounts it on an element with
  `_meta={"subbuilder": "db_class:grammar"}` and writes the database under that
  element starting from `db()`. `AsqueelDb(node)` builds the database from the
  resulting `db` node; model and connection settings equal those of a standalone
  recipe calling the same function. See "Mount Asqueel in a host configuration"
  in the configuration grammars guide.
- Changed messages: the compiler reports `Unsupported asqueel expression syntax`
  (was `Genro`), and the catalog importer warns that a type `has no asqueel code`
  (was `Genro code`). Code matching those texts must be updated.

Validation: 850 tests passed on PostgreSQL and SQLite, with 95% coverage.
CI passed ruff, mypy and the strict documentation build.

## 0.4.0

Released on PyPI and tagged `v0.4.0`.

- Ordinary update/delete now always require exactly one record and a declared
  primary key, independently of hooks. Existing multi-row callers must explicitly
  use raw_update/raw_delete when bypassing Python table triggers is intended.
- raw_insert accepts a mapping or a list, with combined results and no implicit
  commits. Raw predicates remain multi-row even with shared DB hooks; those hooks
  receive supplied operation data, without a loaded old-record snapshot.
- Fixed composite foreign-key projection into migration metadata, including
  unnamed relations and remapped physical columns.
- Connection implementation now inherits the DB setting unless explicitly
  overridden, so a SQLite DB cannot silently take the PostgreSQL default.
- Removed the internal Session entity. Database directly owns execution,
  completion, callbacks and cleanup; named connections keep only per-thread data.
- Request lifecycle and callback recovery verified on PostgreSQL and SQLite:
  callback exceptions reach the application, which owns recovery and cleanup.
- Date and locale defaults follow the documented context-only contract, without
  Babel or locale validation.
- `IN :ids` and `NOT IN :ids` bind a collection (`list`, `tuple`, `set`,
  `frozenset`) as one parameter per member, in compiled queries and in direct
  SQL. An empty collection renders an operand-free form that never emits
  `IN ()`. Mixing one parameter between collection and scalar position is an
  error. PostgreSQL `= ANY(:ids)` with a list keeps binding one array parameter.
- Queries accept `distinct`, `group_by` and `having`, resolved like `where`.
  Unsupported combinations — `having` without `group_by`, `group_by='*'`,
  `for_update` or `exclude_logical_deleted='mark'` with distinct/grouping, and
  an ORDER BY item that DISTINCT cannot project — raise
  `UnsupportedFeatureError` on both backends.
- `SqlQuery.count()` is implemented: one statement, a Python `int`, row policies
  applied as for `fetch()`, ORDER BY dropped and `for_update` ignored. It wraps
  the select in a subquery when the projections are not plain column references,
  and rejects a query carrying `limit` or `offset`.
- Breaking: the `params=` mapping argument is removed from every public query,
  record, write and compiler entry point, and from formula subquery definitions.
  Pass parameters as keyword arguments (`minimum=100`) or as the legacy-named
  `sqlparams={...}` mapping. A leftover `params=` on `query()` is reported as an
  unused keyword binding; on the write and compiler methods it is a `TypeError`.

Validation: 845 tests passed on PostgreSQL and SQLite, with 95% coverage.
Ruff, mypy and the strict documentation build passed.

## 0.3.0

Released on PyPI and tagged `v0.3.0`. This release changes transaction completion in the former
low-level runtime: callers must now commit or roll back explicitly.

- One execution implementation for AsqueelDb and the lower-level facades. Direct
  SQL supports bound `:name` and environment parameters. Execute never commits
  automatically; transaction objects and connection contexts have been removed.
- Environment, named connections and write state are isolated per thread.
  Each worker releases its own connections with `closeConnection()` or `close()`.
- Write orchestration lives on the DB. Table methods delegate; raw variants skip
  table hooks but retain shared DB hooks and change tracking. Extension points
  are documented in the hook guide and legacy adaptation map.
- SQLite runtime and CLI migration support reuse the existing migration adapter.
  Attached schema files and immediate transactions have explicit concurrency and
  DDL limitations; see the SQLite guide.
- AsqueelDb copies supplied environment defaults per thread. Standalone executors
  can still share an explicitly supplied SqlEnvironment with a compiler.

Validation of this checkout: 618 tests passed against PostgreSQL and SQLite,
including the installed wheel and executable examples; coverage 95%.

## 0.2.0

Version prepared in the source repository; package publication is a separate
step. This version introduces the configuration-to-terminal workflow:

- `AsqueelDb("name")` is the public configured database class. The previous
  `build_database(...)` factory remains available for compatibility.
- Register configuration folders under `~/.asqueel`, or relocate the registry
  with `ASQUEEL_HOME`. Registry cards store paths, not credentials.
- Declare the singleton `connection` section using standard `EnvResolver`
  attributes. Existing `conninfo` / `connect_kwargs` recipes remain supported.
- Use the `asqueel` CLI to check configurations, plan/apply PostgreSQL
  migrations and open a Python console with `db` available.
- Follow the executable [two-schema example](two-schemas.md), covering users,
  access logs, customers, products, invoices and rows with separate model/logic.
- Python write failures are attributed to the correct connection; stale SQL
  exceptions cannot bypass rollback-only protection, and database scope
  cleanup preserves the original exception if cleanup also fails.

Reads/writes use the PostgreSQL runtime. SQLite runtime support is planned;
the existing migration package already has PostgreSQL, SQLite, MySQL and SQL
Server adapters. The CLI preserves the migrator's supported removal behavior.
See [current status](limitations.md) and the [CLI guide](cli.md) for boundaries.

Validation for this implementation: 584 tests passed on isolated PostgreSQL,
including executable documentation and installed-wheel checks; coverage 95%.
