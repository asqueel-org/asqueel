# Release notes

## 0.4.0

Version prepared in the source repository; package publication is separate.

- Removed the internal Session entity. Database directly owns execution,
  completion, callbacks and cleanup; named connections keep only per-thread data.
- Request lifecycle and callback recovery verified on PostgreSQL and SQLite:
  callback exceptions reach the application, which owns recovery and cleanup.
- Date and locale defaults follow the documented context-only contract, without
  Babel or locale validation.

Validation: 650 tests passed on PostgreSQL and SQLite, with 95% coverage.
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
- Python write failures are attributed to the correct session; stale SQL
  exceptions cannot bypass rollback-only protection, and database scope
  cleanup preserves the original exception if cleanup also fails.

Reads/writes use the PostgreSQL runtime. SQLite runtime support is planned;
the existing migration package already has PostgreSQL, SQLite, MySQL and SQL
Server adapters. The CLI preserves the migrator's supported removal behavior.
See [current status](limitations.md) and the [CLI guide](cli.md) for boundaries.

Validation for this implementation: 584 tests passed on isolated PostgreSQL,
including executable documentation and installed-wheel checks; coverage 95%.
