# Changelog

## 0.6.0 — Unreleased

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
- Bag and Builders are constrained to the 0.27 series to preserve the legacy XML
  importer. The source distribution and installed-wheel verification include
  the hierarchical invoice migration JSON fixture.

Migration remains a separate optional dependency, now requiring the published
`asqueel-migration>=0.2.2,<0.3`. CI pins 0.2.2, which includes UNIQUE removal
using real constraint/index names and `serial4` support. See
[RELEASING.md](RELEASING.md) for dependency and publication checks.
Asqueel core 0.6.0 itself remains unreleased.
