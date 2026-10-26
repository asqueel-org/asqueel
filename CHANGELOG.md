# Changelog

## 0.9.0 — Runtime per call

- `AsqueelDb` holds the model and the configuration shared by every call.
  `SessionDb`, exported from `asqueel`, holds the connection, `currentEnv`,
  trigger stack and transaction state of one call (#56).
- `db.session(name=None, *, target='main', **env)` returns the `SessionDb` of
  the current call: the main one (`'_main_connection'`) or the one called
  `name`, connected to the configured connection `target`. `SessionDb.close()`
  rolls back and closes it; a `SessionDb` is a context manager closing at exit.
  `AsqueelDb.close()` closes every open session of the database.
- The shared `AsqueelDb` holds no connection: `execute`, `commit`, `rollback`
  and table writes on it raise `TransactionStateError`. A closed `SessionDb`
  refuses any use; concurrent use of one `SessionDb` raises.
- Per-thread state is removed: the current session of a call lives in a
  `ContextVar` of the `AsqueelDb`. Each `contextvars` context is a separate
  call; on a reused worker thread, a call whose sessions are closed is followed
  by a new call with new sessions. A `SessionDb` may move between threads of
  its call; concurrent use of one session (a statement, a fetch, a commit, a
  close) raises `TransactionStateError`. Each asyncio task needs a session of
  its own.
- A clean close of a session after a write, or with deferred callbacks still
  queued, rolls back and logs a warning on the `asqueel.application` logger;
  a session that only read closes without it, and a close by exception rolls
  back without it. A close refused while a statement or a commit is in
  progress changes nothing.
- A session of an `AsqueelDb` subclass has the subclass's methods, but the
  subclass's `__init__` does not run for it: instance state lives on the
  shared database, reached as `session.shared`.
- `closeConnection()` keeps its meaning on a `SessionDb`: roll back, close the
  connection, the next statement opens a new one.
- `tempEnv(connectionName='x')` runs the block's statements on the connection
  of the call's session `x`, opened on first use on the configured connection
  `x` (`main` when the recipe declares no named connection), as before; it
  closes with the session that opened it. `db.session('x', target='x')` opens
  the same session explicitly.
- SQLite `:memory:`: the `AsqueelDb` keeps one connection and lends it to one
  session at a time; a second open session raises `TransactionStateError`.
  `closeConnection()`, the close of a session and `migrate()` keep its data,
  `AsqueelDb.close()` discards it; work a session left uncommitted is rolled
  back when the connection is lent again. SQLite connects with
  `check_same_thread=False`.
- `AsqueelDbMixin`: `owner.db` and `owner.get_db(name)` return the main
  `SessionDb` of the call; `release_databases()` closes the sessions of the
  calls the owner opened, the named ones included, also when the application
  already closed the main one. A session that refuses to close stays tracked
  and the next release closes it. `taken_databases` lists `SessionDb`
  instances.
- pgbouncer is supported in `session` pool mode only.
- Deprecated: the module-level `asqueel.session(db, **env)`, now an alias of
  `db.session(**env)`, kept for this release only.
- PostgreSQL: every `%` outside a binding is doubled before execution, also
  when the statement has no parameters (#19). Application SQL that wrote `%%`
  to obtain a literal `%` must now write `%`.
- An update whose record has a key named `__pkey__N` raises `ValueError`
  instead of binding it over the primary key (#24).

## 0.8.0 — Legacy grammar names and TYTX sources

- A recipe source is saved with `recipe.source.to_tytx()` and loaded with
  `AsqueelDb('<file>.tytx')`: the `db` node is replayed into a new recipe, so the
  grammar validates it. `SqlSourceBag` is registered as a TYTX subtype;
  environment resolvers stay resolvers. Requires `genro-tytx>=0.16.4`.
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
- Table options take the legacy names: `sys_fields` becomes `sysFields`,
  `auto_counter` becomes `counter`, `relative_index` becomes `relidx`,
  `dynamic_fields` becomes `df` (table option and column element),
  `full_update` becomes `fullUpd`, `system_records` becomes `sysrecords`.
  The old names are no longer in the grammar.
- The table options `record_hash`, `audit`, `protection` and `attachments`
  leave the grammar with their expansions; declaring them raises
  `AttributeError`. A model that used them declares the columns it needs.
- `schemas` and `schema` leave the grammar: a model starts only from
  `packages().package(...)`. A former `schemas().schema('x', sqlname='p')`
  becomes `packages().package('x', sqlschema='p', sqlprefix=False)`.
  `SqlModelReader` mounts one such package per schema of the structure; a
  multi-column primary key becomes a `compositeColumn` named as the pkey.
- `relation` takes the legacy parameter names: `to` becomes `related_column`,
  `case_insensitive` becomes `insensitive`.
- The `x_*` parameters leave the grammar: `table` loses `x_table_class`,
  `x_expanded_legacy` and `x_logical_pkey`; the columns lose `x_identity` and
  `x_generation`; `relation` loses `x_weak`, `x_canonical` and `x_name`. The
  source and the live model carry no `x_*` attribute.
- A table gets its own class only from the package layout:
  `package(name, path=<folder>)` loads `<folder>/model/<table>.py`, whose
  `Table` class, combined with `SqlTable`, is the runtime table.
- The module `asqueel.legacy_source` (the expanded legacy XML loader) is removed.
- Without `x_identity`, `ResultColumn.source` is the column fullname.
- The grammar checks `retention.days >= 0`, `hierarchical.depth >= 1`,
  `driver.connect_timeout`, `driver.timeout` and `driver.cached_statements >= 0`
  and a string `package.sqlprefix` (nonempty, no trailing `_`) at declaration;
  a violation raises the genro_builders `ValueError("Validation failed: ...")`.
- `column` declares the six `sql_pg_*` and `sql_sqlite_*` parameters
  explicitly; `validate_*` stays the only open attribute family.
- `SqlModelValidator` keeps only the referential checks. The composed
  source is re-validated node by node against the grammar, so an attribute
  outside it raises even when written after the call: by `set_attr`, by
  `Package.config_attributes()` or by `custom_type_<dtype>()` of a package layout.
- A package layout module runs once per model build and is registered in
  `sys.modules`; `hierarchicalHandler` exists only on hierarchical tables.
- `SqlModelReader` refuses the logical dtypes `P`, `X` and `Z` in a physical
  structure.
- `connection_settings` moves from `asqueel.configuration` to `asqueel.runtime`.

## 0.7.0 — Consolidation and unified model candidate

- Use the hierarchical `DbModel` for authored models, PostgreSQL catalog imports,
  JSON loading, SELECT/write compilation and physical migration projection.
- Remove the disconnected `ResolvedModel`, `Column`, `Table` and `Relation`
  descriptors and their separate migration projection. Imported models now use
  qualified table names and the same key/relation API as authored models.
- `model_to_json` and `model_from_json` round-trip the live hierarchy using the
  version 2 `asqueel-model` format. Connections and executable Python objects
  are excluded; the former descriptor format is not accepted. Re-export from
  the source recipe or inspect the catalog again.
- Preserve catalog warnings and all refusals of lossy physical projections.
  No query features or optimizations are added in this release.

- Preserve parameter-like text inside SQL strings, quoted identifiers and comments,
  including scoped formula bindings and environment parameters (#35).
- Cover PostgreSQL dollar/E strings, nested comments, SQLite quoting, adjacent
  parameters and collection expansion with regression and live database tests.
- Correct the alias handle, zero limit, missing environment value and SQL/application
  cascade documentation (#27, #37).

## 0.6.3 — 2026-10-21

- Remove upper version bounds on internal tools (Builders, Bag and Migration).
  Run the complete CI matrix with the latest published ecosystem dependencies
  so incompatibilities surface instead of being hidden by frozen versions.

## 0.6.2 — 2026-10-21

- Preserve explicit column and relation defaults independently of other
  declarations. In particular, `sys_fields()` keeps `indexed=False` after
  unrelated columns are added, including in migration output.

## 0.6.1 — 2026-10-20

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

## 0.6.0 — 2026-10-20

- Data files: `query(...).fetch(destination=)` writes the rows to a CSV, JSON
  or TYTX file in blocks and returns the row count; `table.sql_insert(file)`
  inserts such a file in blocks. The format comes from the extension or
  `format=`. `adapt=` (default on for files) converts untyped values through
  the overridable `table.adaptRecord(record)`.
- SQLite `:memory:` migrations reuse the application's connection, preserving
  tables and data across planning, DDL and verification without creating files.
  `reloadModel(source)` lets an idle, exclusively used in-memory REPL session
  adopt an updated model before migrating again; a relation added to an
  existing table migrates with `foreignKeys=False`. Old table/query
  handles are invalidated; pending work must be committed or rolled back first.
- Native model source, option expansion and migration JSON cover the 74 included
  `test_invoice_pg` models. The hierarchical object renderer and its query
  compiler coexist with the previous renderer/compiler.
- Hierarchical SELECT compilation and fetch/count use the model's relation tree,
  formulas and subqueries. To-many operations still have no implemented handlers.
- `fetch()` returns mutable Toolbox `NamedList` rows, with access by column name
  and position, on both PostgreSQL and SQLite. Code requiring actual `dict` rows
  must explicitly convert them, for example with `dict(row.items())`.
- Symbolic WHERE parameters on the hierarchical compiler retain legacy
  `embedFieldPars` behavior; the previous compiler binds those strings literally.
  See [the parameter guide](docs/guide/queries.md#symbolic-parameters-and-external-values)
  for external values and the legacy escape convention.
- Dependency baseline: `genro-bag>=0.28.0,<0.29`,
  `genro-builders>=0.29.0,<0.30` and optional
  `asqueel-migration>=0.3.1,<0.4`. See [RELEASING.md](RELEASING.md).

Published on PyPI on 2026-10-20 from tag `v0.6.0`.
