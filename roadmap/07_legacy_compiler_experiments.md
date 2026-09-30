# Legacy Inventory — SQL Compiler Improvement Experiments (genropy, Feb–Mar 2026)

**Version**: 0.1.0 · **Last Updated**: 2026-07-08 · **Status**: 🔴 DA REVISIONARE

Inventory of the experiments run on the legacy SQL compiler in the
genropy repository (github.com/genropy/genropy) between February and
March 2026: attempts to improve the compiler and to exploit mechanisms
other than correlated subqueries. Sources: branches, pull requests and
issues of the genropy repo, verified on 2026-07-08.

**Key fact**: none of the experimental code is in `develop` —
`SqlCompiledSubQuery`, `sq_as_join`, `SqlCompoundQuery` and
`compiler_new` are all absent from the branch (verified with
`git grep` on `develop`). The experiments survive only in the branches
and PRs listed below; two PRs are still open (#542, #544). What DID
land in `develop` from the same period is the surrounding
infrastructure (see §3).

---

## 1. The "subquery improvement" chain (the main thread)

A sequence of superseding attempts, all by the same author, aimed at
(a) restructuring how virtual columns / subqueries are compiled and
(b) converting correlated inline subqueries (N+1 pattern) into
pre-aggregated JOINs.

| Step | PR / branch | Date | State | Content |
|---|---|---|---|---|
| 1 | **PR #457** `feature/query-extended-use` | 2026-02-06 | closed | `SqlCompoundQuery` — set operations (UNION / INTERSECT / EXCEPT) over `SqlQuery`, plus the "mangler" infrastructure (alias-name mangling so member queries can be combined). Follow-up branch `feature/compound_query` (2026-02-16): standalone `SqlCompoundQuery` + `mangler`/`query_kw` support in `SqlQuery` and `SqlQueryCompiler`, 344 lines of tests (`test_compound_query.py`). |
| 2 | **PR #458** `improve_subquery_implementation` | 2026-02-07 | closed ("ON HOLD", superseded by #460) | Linear dispatch of virtual columns in `getFieldAlias` (relation_path → formula → py_method → error) replacing the monolithic inline handling; mangle ownership moved from the compiler to the compiled query (mangling previously worked by side-effect on the shared `sqlparams` dict). **Bug found during the work**: the "formula + single subquery" case (e.g. `COALESCE(#default, 0)`) was silently ignored in the single-subquery path. |
| 3 | **PR #460** `improve_subquery_implementation_v3` | 2026-02-08 | closed | Unified subquery dispatch + new `SqlCompiledSubQuery` class (subqueries as first-class compiled objects instead of inline strings). |
| 4 | **PR #461** `subquery_to_join` | 2026-02-08 → 11 | closed ("superseded — will be recreated") | **Subquery-to-JOIN transformation**: correlated inline subqueries converted into pre-aggregated `LEFT JOIN` subqueries. Activation with a 3-level priority chain: per-column `formulaColumn('x', sq_as_join=True, select=dict(...))` > per-query `query(..., enable_sq_join=True)` > global `GnrSqlDb(..., subquery_as_join=True)`. Also: `expandThis`/`expandPref`/`expandEnv` promoted from closures inside `getFieldAlias` to compiler methods (enabling `#THIS` in legacy `sql_formula` with inline subselects); fix for the `#dflt` placeholder not being substituted when `formulaColumn` has only `select=dict(...)` without an explicit `sql_formula` (the most common production pattern). |
| 5 | **PR #471** `feature/subquery_improvement` | 2026-02-11 | closed | Consolidation attempt: subquery-to-join + compound queries + cross-formula fix in one PR. |
| 6 | **PR #544** `feature/subquery_refactor_v3` | 2026-02-19 | **OPEN** | "Subquery-as-join conversion and compound queries" — the last consolidated form. Commits: `SqlCompiledSubQuery` + subquery infrastructure, `expandThis/Pref/Env` as class methods, `_handleFormulaColumn` + subquery-as-join conversion, `sq_joins`/`sq_compiled_dct` integrated into `compiledQuery`, `SqlCompoundQuery` tests. Local continuation branches: `feature/subquery_refactor_v3_merged` (2026-02-26, adds the `sql_aggregate` flag for many-side relation subqueries, issue #496) and `feature/subquery_refactor_v4` (2026-02-28, adds the `normalize_subquery_dict` preprocessor). |
| 7 | **branch `feature/subquery_refactor_v2`** | 2026-02-19 | local branch | The most architectural variant: extraction of `CompiledColumn`, `AliasManager` and `ColumnCompiler` from the monolithic `SqlQueryCompiler`; a `SubqueryEntry` registry with lazy subquery rendering ("Fase 1+2"); deep cross-join torture tests with **LATERAL detection** (`test_torture_compiler.py`, 598 lines) and where/order-by subquery tests. |

Reading of the chain: v1 (#457/#458) restructures, v3 (#460/#544)
introduces the compiled-subquery object and the JOIN conversion, v2
(despite the name, dated later) decomposes the compiler into
collaborating objects. The activation flags (`sq_as_join` per column)
show the intent to roll out the JOIN strategy incrementally without
changing default behavior.

## 2. Parallel threads (same period)

- **Shadow compiler** — branch `feature/compiler-simplify`
  (2026-02-27): `compiler_new.py` (1,518 lines) added side-by-side with
  the old compiler, switchable at runtime via
  `currentEnv['use_new_compiler']`; both `query.py` and `record.py`
  import both classes and pick per-query. The relation tree
  (`gnrsqlmodel/resolvers.py`) is extended so it contains **all**
  virtual columns (not only those carrying a `.relation()`), and
  `getFieldAlias` warns when a column resolved via `getVirtualColumn`
  is missing from the relation tree. Pattern worth keeping: a shadow
  implementation validated by divergence warnings against the live one.
- **RuntimeColumns / RuntimeModel** — issue #496 (2026-02-17) + PR
  #542 (**OPEN**) + branch `feature/runtime_virtual_columns`:
  programmatic injection of temporary virtual columns and relations
  into a query scope via `rc = db.runtimeColumns()` …
  `with db.tempEnv(_runtime_columns=rc):`. Motivation: tests,
  ad-hoc computed columns, prototyping formula columns without
  touching the model. Includes a 782-line virtual-column stress test
  (`test_virtualcolumn_stress.py`) reused by the subquery_refactor
  branches.
- **Lazy selection** — issue #488 (2026-02-14) + branch
  `feature/lazy_selection`: `SqlSelection` defers the fetch until first
  data access, and an `_outputTable` sqlparam turns a query into
  `CREATE TABLE AS SELECT` (materialization instead of fetch).
- **Coverage and dead-code mapping** — issue #470 (2026-02-11,
  "Missing SQL coverage in develop"); PR #551 (merged 2026-02-20,
  252-test compiler coverage suite with partition/subtable/staff); PR
  #647 (merged 2026-03-03, coverage to 92% **with dead-code
  annotations** in the compiler); branches
  `feature/compiler_100_coverage`, `feature/increase_compile_test`,
  `feature/relations_dbenv` (179 runtime tests on PG+SQLite, subtable
  and partition suites, SQLite `IS NOT TRUE` NULL-handling fixes).
- **Macro registry** — issue #617 + PRs #650/#660 (merged 2026-03-03/04):
  extensible `db.addMacro()` registry replacing hard-coded macro sets;
  `#BETWEEN` renamed `#IN_RANGE` (issue #622, merged); VECQUERY/VECRANK
  pgvector macros (issue #583, merged) and the `RE_SQL_PARAMS` fix for
  the PostgreSQL `::` cast operator (issue #585, merged).
- **Relation-tree thread-safety** — issue #548 + PR #578 (merged
  2026-02-25): removal of the redundant double cache and unsafe
  locking in `RelationTreeResolver`; the tree is cached per-request in
  `currentEnv`.
- **Compiler review cluster** — ten issues opened on 2026-02-28 as the
  outcome of the coverage work, all still open. They are point-by-point
  verdicts on compiler features: `table_aliases` undocumented/untested,
  evaluate (#616); `#ENV()` macro has zero usage, deprecate in favor of
  `:env_*` bind params (#618); auto-discover `sql_formula_<name>`
  methods without the `sql_formula=True` double declaration (#619);
  document the subquery string-delegation pattern
  (`select='method_name'` → `subquery_<name>()`) (#620); `join_on` in
  the joiner is unreachable from the model API, `between` and
  `case_insensitive` joins appear unused (#621); `*@relation` glob in
  `expandMultipleColumns` has zero usage, deprecate (#623); move the
  multi-store `_STORENAME_` injection out of the compiler (#624);
  redesign `joinConditions` — 3 API levels, 5 compiler code blocks,
  2 keying strategies — unifying runtime and declarative join
  filtering, possibly over `join_on` (#625).

## 3. Merged vs not merged

**Landed in `develop`** (infrastructure that the rewrite can treat as
current legacy behavior):
`gnrsqldata.py` split into a documented sub-module package (PR #490,
2026-02-15); the coverage suites (PRs #551, #647, plus #552 —
162 structural gnrsqlmodel tests); the macro registry (PRs #650,
#660); `#IN_RANGE` rename (#622); thread-safe relation tree with
`currentEnv` cache (PR #578); `feature/join-conditions-refactor`
(merged into develop).

**Never landed (the experiments proper)**: `SqlCompoundQuery`,
`SqlCompiledSubQuery`, subquery-as-join (`sq_as_join`/`enable_sq_join`/
`subquery_as_join`), `compiler_new.py`, the
`CompiledColumn`/`AliasManager`/`ColumnCompiler` decomposition,
`SubqueryEntry` lazy rendering, RuntimeColumns/RuntimeModel, lazy
selection / `CREATE TABLE AS SELECT`. They live only in the branches
and PRs above (PRs #542 and #544 still open).

## 4. Relevance for the asqueel rewrite (pillar 4 inputs)

1. **Subquery-to-JOIN as a first-class compile strategy.** The legacy
   compiles every `formulaColumn(select=...)` as a correlated inline
   subquery (N+1). The #461/#544 work proves the transformation to
   pre-aggregated LEFT JOINs is feasible on the legacy model and maps
   the hard cases (`#THIS` expansion, `#dflt`, aggregation on the many
   side via `sql_aggregate`). The new compiler should treat the
   rendering of a virtual column (inline subquery vs join vs LATERAL)
   as a **strategy chosen at compile time**, not as the column's
   identity.
2. **LATERAL is on the map** (subquery_refactor_v2 torture tests) —
   the third rendering strategy beside inline subquery and
   pre-aggregated join.
3. **Compound queries** (UNION/INTERSECT/EXCEPT) exist as a designed,
   tested surface (`SqlCompoundQuery` + mangler). The grammar/compiler
   contract of the rewrite should reserve room for query composition.
4. **Compiler decomposition** — `CompiledColumn`, `AliasManager`,
   `ColumnCompiler`, `SqlCompiledSubQuery` are the seams the legacy
   author identified inside the monolith. They are a validated starting
   point for the new compiler's object model.
5. **Extensible macro registry** (`db.addMacro`, merged) is the
   current macro architecture — the rewrite inherits this design, not
   the old hard-coded sets.
6. **Relation tree containing all virtual columns**
   (compiler-simplify) anticipates the rewrite's own decision: the
   single source tree carries every column kind, and consumers filter.
7. **Deprecation list ready** (#616–#625): `table_aliases`, `#ENV()`,
   `*@relation` glob, joiner `between`, unreachable `join_on` are
   candidates for NOT porting; `joinConditions` needs the unified
   redesign of #625; `_STORENAME_` injection must not live in the new
   compiler (#624).
8. **Shadow-compiler rollout pattern** (`use_new_compiler` env switch,
   divergence warnings) is a proven migration technique if the new
   compiler ever needs to run inside legacy genropy for validation.

---

## Riferimenti

- Recovery session: 2026-07-08, verified against
  `github.com/genropy/genropy` (issues/PRs via `gh`) and the local
  clone `/Users/gporcari/Sviluppo/Genropy/genropy` (branches, diffs).
- PRs: #457, #458, #460, #461, #471, #490, #542 (open), #544 (open),
  #551, #552, #578, #647, #650, #660.
- Issues: #470, #488, #496, #541, #548, #583, #585, #616–#625.
- Branches (local unless noted): `feature/compound_query`,
  `feature/subquery_refactor_v2`, `feature/subquery_refactor_v3`
  (origin), `feature/subquery_refactor_v3_merged`,
  `feature/subquery_refactor_v4`, `feature/compiler-simplify`,
  `feature/compiler_100_coverage`, `feature/runtime_virtual_columns`,
  `feature/lazy_selection`, `feature/relations_dbenv`.
