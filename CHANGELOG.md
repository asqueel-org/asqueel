# Changelog

## 0.6.4 — Consolidation candidate

- Preserve parameter-like text inside SQL strings, quoted identifiers and comments,
  including scoped formula bindings and environment parameters (#35).
- Cover PostgreSQL dollar/E strings, nested comments, SQLite quoting, adjacent
  parameters and collection expansion with regression and live database tests.
- Correct the alias handle, zero limit, missing environment value and SQL/application
  cascade documentation (#27, #37).
- Keep the published model and JSON contracts; the unified model is reserved for 0.7.

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
