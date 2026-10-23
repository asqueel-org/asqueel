# Roadmap

Cleanup of the unauthorized differences from GenroPy legacy, decided with the user on 2026-10-17. Rule: legacy unless the user decided otherwise; anything outside the grammar raises; this release is the low-level SQL layer. Full decisions: local untracked `temp/audit-invenzioni/decisioni.md`; inventory `docs/design/112-legacy-inventory.md`.

## Macro 1 (done): genro-builders 0.29 and db.adapter — done/adapter-base/plan.md

## Macro 2 (done): silent behaviours and "outside the grammar raises" — done/silent-behaviours/plan.md
- Objective: no legacy declaration is accepted and ignored. Fix the easy silent ones as legacy; make every deferred feature raise with an error that names it.
- Starts from: Macro 1 landed (`db.adapter`).
- Ends at: `name::dtype`, `relation_name=`, `limit=0`, `onDelete_sql=`/`onUpdate_sql=`, SQLite value types and deferred SQLite transactions behave as legacy; multi_tenant, subtable, totalizer, package triggers, sql_comment, env conditions and every other deferred input raise; `UnsupportedFeatureError` generic messages replaced by specific errors.
- Delivers: a grammar that fails loudly; consumed by every later macro.
- Consumes: the adapter (SQLite types and transactions live there).
- Requires of earlier work: the adapter owns connection and type conversion.
- Open decisions: none beyond decisioni.md.

## Macro 3 (done): hierarchical tables — done/hierarchical-tables/plan.md
- Objective: hierarchical tables work for reads (macros) and writes (tree-maintaining triggers), declared with `options().hierarchical(...)`, result very close to the legacy; triggers in a mixin or proxy; consider the algorithm improvements of `docs/design/36-hierarchical-analysis.md` if not risky.
- Starts from: Macro 2 landed.
- Ends at: a hierarchical table is readable and writable on both dialects (#30 closed).
- Open decisions: settled 2026-10-18 in the plan (proxy as legacy; doc 36 §10.2 last position on move, 1296th sibling error, locked max + 1; sys_fields write #29 included; text_pattern_ops moved to Macro 7).

## Macro 4 (done): model in legacy syntax — done/model-legacy-syntax/plan.md
- Objective: model declarations back to the legacy spelling where the user did not decide otherwise (indexed/unique strings, UI attributes, compositeColumn and composite pkey, index(), one_one, cnd/join_on/between, custom_type, name_long..., config_db, table kwargs lastTS/draftField/logicalDeletionField, partition_<field>, unknown names returning None); `options()` stays for sysFields/dbo (user decision); `sql_default`, `sql_generatedExpression`, `sql_extra` (+ `sql_pg_*`).
- Starts from: Macro 2. Ends at: legacy model sources load unchanged within the low-level scope.

## Macro 5 (done): query — done/query-legacy/plan.md
- Objective: formulaColumn_<name>() table methods as legacy (dynamic columns, legacy gnrsqlmodel/table.py:405; they raise from Macro 2), formulaColumn (dtype A, sql_formula=True, select_<name>, exists_<name>, error on sql_formula with select/exists), subQueryColumn with `aggr=`, fetch and derivatives, `fetchRecord()` (legacy record() out of this release), #ENV/#BAG/#BAGCOLS, compiled/sqltext cache and test(), kwargs warning, compositeColumn as a value (#26).
- Starts from: Macro 4. Ends at: legacy queries of the low-level scope run unchanged.

## Macro 6 (done): read-write and transactions — done/read-write-legacy/plan.md
- Objective: low-level write cycle as legacy (delete reread through fetchRecord, pkey composite, insertOrUpdate, Bag in X, currentEnv/workdate/locale, connections, deferToCommit in currentEnv, db.execute returning the cursor, lock, for_update modes, setConstraintsDeferred, analyze/vacuum, onDbCommitted hook, logical-delete cascade); `query().update()`/`query().delete()` through triggers beside `sql_update`/`sql_delete`; connection API identical to legacy (close/with/acquire/outcome removed; EnvironmentMismatchError already removed by Macro 5); `sql_insert(record | list)` assigning pkeys.
- Starts from: Macro 5 (fetchRecord).
- Requires of earlier work (Macro 5 quality check): `session(db)` (user's name, 2026-10-19), a context manager marking a unit of work outside a request — on entry `clearCurrentEnv()` with optional initial env values, on exit `closeConnection()`, as the GenroPy page request does (`gnrwebpage.py:161`, `gnrwsgisite.py` cleanup); it is not `with db:` (A6.22). Open: explicit rollback on exit or left to the close; nested sessions. The dynamic-column cache in `currentEnv` (Macro 5) lives one session. Also: a driver error raised while reading from `cursor()`/`servercursor()` does not mark the connection failed; settle it with the automatic rollback on SQL errors.

## Macro 7 (done): migration and dialects — done/migration-dialects/plan.md
- Objective: migrate() stops and explains skipped changes, final check and explicit refusals stay; SQL action abbreviations; index on relation columns; `indexed={...}` and index(); `foreignKeys=False` migration option; conversion of filled columns with backup; SQLite attach as legacy; SQLite FK on by default and switchable; dtype SQL types as legacy; capability catalogue proposal (by theme, analytic capabilities); sqlglot transpilation as a documented proposal. Index operator classes left the macro on 2026-10-19 (see Debts).
- Starts from: Macro 6.
- Requires of earlier work (Macro 4 quality check): SQL index names are hashed by the migrator for default-named `index()` nodes and taken from the name for explicit ones (`migration.py`, `object_tree_projection.py`); legacy never passes `index_name` (`orm_extractor.py:465`), so every legacy index is hashed. Decide this rule before building `indexed={...}` and the index projection: a database migrated from legacy sees explicitly named indexes as different. `vacuum()` on SQLite runs `VACUUM` on the main file only; with SQLite attach (this macro) decide whether attached schema files are vacuumed too (Macro 6 quality check).

## Macro 8 (done): comparison document — done/differences-document/plan.md
- Objective: Sphinx chapter (English) and new team page (Italian) in the agreed form: Differences → Model / Query / Read-Write → missing (temporary, removed, replaced) / different / new / same, plus "to implement" as its own branch; cards "in GenroPy you wrote / got" above, asqueel below; one label; low-level vs high-level API; proposals (sqlglot, .sql(), capability catalogue, async).
- Starts from: Macros 2-7 landed.

## Macro 9 (current): model cleanup — detailed in active/model-cleanup/plan.md
- Objective: one construction path and one database class in the legacy order (`AsqueelDb` first, its model rendered into it through `builder.render(target=db)`); the migration structure and the Python recipe rendered from the source by `RendererBase` renderers; `sqlname` always applied.
- Starts from: Macro 8 and the first cleanup commits on `release/consolidation` (catalog import and model codec removed, dead code removed, one spelling per declaration and for the environment API), head f8b68f4.
- Ends at: `AsqueelDb(source)` is the one constructor; modes `objects`, `migration`, `python` on `SqlBuilder`; `Database`, `SqlDatabase`, `SqlEnvironment`, `projection.py`, `object_tree_projection.py`, `to_physical_builder`, `emit()` gone.
- Delivers: the `structure-1.0` renderer from the source, consumed by the move of the database-reading code to asqueel-migration (next cleanup step).
- Open decisions: the construction form (`AsqueelDb(source)`, `main` on an `AsqueelDb` subclass) is a provisional user decision of 2026-10-22, to be reviewed.

## Debts
- `text_pattern_ops` on the `hierarchical_pkey` index and column collation (2026-10-19). Legacy has neither. Measured on PostgreSQL 17: with a non-C database collation a prefix `LIKE` on `hierarchical_pkey` scans the table; with collation `C` it uses the UNIQUE index. Proposed in the legacy first: genropy/genropy#1708 (collation, `unaccent='full'`), measurement on genropy/genropy#1526. asqueel follows the legacy outcome.
- Alias relations and composite columns (2026-10-22, Macro 9 decisions D6 and D6-bis). Legacy resolves `@alias.x` at query time (`gnrsqlmodel/table.py:541-542,614-645`) and keeps a composite column as a virtual column with `composed_of` (`gnrsqlmodel/model.py:1050`); asqueel registers alias relations at build time (`_inherit_alias_relations`) and keeps composites in their own `composites` container. Moving either changes the query and write compilers and the source container; it goes with the grammar step.
