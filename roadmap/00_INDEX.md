# asqueel — Design Documentation Set

**Version**: 0.2.0 · **Last Updated**: 2026-07-08 · **Status**: 🔴 DA REVISIONARE

Documentation set for the rewrite of the Asqueel engine as a
genro-builders dialect. Documents keep the 🔴 status until reviewed
and approved (🟡 / 🟢).

| Doc | Content |
|---|---|
| [01_legacy_model_grammar.md](01_legacy_model_grammar.md) | Exhaustive inventory of `DbModelSrc` (every grammar method with real signatures), attribute inventory (physical vs semantic), `addRelation` analysis, runtime model objects, 30 rewrite decision points |
| [02_legacy_compiler_query.md](02_legacy_compiler_query.md) | Query language surface (`$col`, `@rel`, `:param`, macros with verbatim regexes), relation-path → JOIN resolution, virtual columns in the compiler, `SqlCompiledQuery`, SqlQuery/Selection/Record API, contract notes; §7 addendum: sizes, consumers, dialect boundary, test map, porting estimate |
| [03_legacy_migration_adapters.md](03_legacy_migration_adapters.md) | Normalized JSON spec, ORM→JSON projection (the model↔migrate contract), DB extractor, diff engine + command builder, adapter DDL surface, dtype tables, planned entities; §7 addendum: runtime coupling, `SqlMigrator`/`SqlModelChecker` coexistence, test/oracle map |
| [04_legacy_tests_inventory.md](04_legacy_tests_inventory.md) | Test-suite map, model fixtures quoted verbatim (video, test_invoice, migration inline models), behaviors pinned per layer, 20-item oracle shortlist |
| [05_grammar_design.md](05_grammar_design.md) | **The design doc**: vision (tree as pivot), agreed decisions, 10 open design questions, implementation plan in slices |
| [06_legacy_adapters_inventory.md](06_legacy_adapters_inventory.md) | Full adapter inventory beyond the DDL surface: file/maintenance status, base API by functional area, duplicated introspection paths (checkDb vs struct_get_*), code-age analysis, call-surface compatibility contract, test map |
| [07_legacy_compiler_experiments.md](07_legacy_compiler_experiments.md) | The 2026 compiler improvement experiments in genropy (branches/PRs/issues, Feb–Mar): subquery-to-JOIN chain, SqlCompoundQuery, compiler decomposition, shadow compiler, RuntimeColumns, review cluster #616–#625 — merged vs unmerged, relevance for the rewrite |

Legacy source of truth for all inventories: Genropy worktree
`/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop` — branch
`fix/websocket-user-events-default-off`, HEAD `83c138bb6`. Doc `07`
additionally references branches/PRs/issues of
`github.com/genropy/genropy`.

Sessions: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06); pillar
investigation and addenda 2026-07-08.
