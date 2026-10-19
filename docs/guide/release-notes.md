# Release notes

## Unreleased

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
  exceptions in `currentEnv['_pendingExceptions']`.
- `AsqueelDbMixin` enters `session(db)` at the first take of a database during
  a call and leaves it in `release_databases()`.

## 0.6.0

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

Validation: 1278 tests passed, 1 skipped, including PostgreSQL application,
introspection and an empty second diff, repeated after controlled schema changes.
Ruff, mypy, the strict Sphinx build and wheel/source-distribution checks passed.
The installed wheel with published dependencies (`asqueel-migration` 0.2.1)
passed 1276 tests with 3 skipped and 95% coverage, including native corpus
migrations. Two additional skips concern `serial4`, which requires migration
engine support unavailable in that published version.
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
  live database and returns a `MigrationPlan` (`commands`, `warnings`,
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
