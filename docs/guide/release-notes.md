# Release notes

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
