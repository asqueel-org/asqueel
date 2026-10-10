# Release notes

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
- Databases per call. `AsqueelDb.acquire()` takes a database for the current
  call: the first take on a thread clears `currentEnv`, and `closeConnection()`
  ends the take. `AsqueelDbMixin` gives a server and its applications databases
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
