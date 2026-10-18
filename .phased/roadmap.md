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

## Macro 3 (current): hierarchical tables — detailed in active/hierarchical-tables/plan.md
- Objective: hierarchical tables work for reads (macros) and writes (tree-maintaining triggers), declared with `options().hierarchical(...)`, result very close to the legacy; triggers in a mixin or proxy; consider the algorithm improvements of `docs/design/36-hierarchical-analysis.md` if not risky.
- Starts from: Macro 2 landed.
- Ends at: a hierarchical table is readable and writable on both dialects (#30 closed).
- Open decisions: settled 2026-10-18 in the plan (proxy as legacy; doc 36 §10.2 last position on move, 1296th sibling error, locked max + 1; sys_fields write #29 included; text_pattern_ops moved to Macro 7).

## Macro 4: model in legacy syntax
- Objective: model declarations back to the legacy spelling where the user did not decide otherwise (indexed/unique strings, UI attributes, compositeColumn and composite pkey, index(), one_one, cnd/join_on/between, custom_type, name_long..., config_db, table kwargs lastTS/draftField/logicalDeletionField, partition_<field>, unknown names returning None); `options()` stays for sysFields/dbo (user decision); `sql_default`, `sql_generatedExpression`, `sql_extra` (+ `sql_pg_*`).
- Starts from: Macro 2. Ends at: legacy model sources load unchanged within the low-level scope.

## Macro 5: query
- Objective: formulaColumn_<name>() table methods as legacy (dynamic columns, legacy gnrsqlmodel/table.py:405; they raise from Macro 2), formulaColumn (dtype A, sql_formula=True, select_<name>, exists_<name>, error on sql_formula with select/exists), subQueryColumn with `aggr=`, fetch and derivatives, `fetchRecord()` (legacy record() out of this release), #ENV/#BAG/#BAGCOLS, compiled/sqltext cache and test(), kwargs warning, compositeColumn as a value (#26).
- Starts from: Macro 4. Ends at: legacy queries of the low-level scope run unchanged.

## Macro 6: read-write and transactions
- Objective: low-level write cycle as legacy (delete reread through fetchRecord, pkey composite, insertOrUpdate, Bag in X, currentEnv/workdate/locale, connections, deferToCommit in currentEnv, db.execute returning the cursor, lock, for_update modes, setConstraintsDeferred, analyze/vacuum, onDbCommitted hook, logical-delete cascade); `query().update()`/`query().delete()` through triggers beside `sql_update`/`sql_delete`; connection API identical to legacy (close/with/acquire/outcome/EnvironmentMismatchError removed); `sql_insert(record | list)` assigning pkeys.
- Starts from: Macro 5 (fetchRecord).

## Macro 7: migration and dialects
- Objective: migrate() stops and explains skipped changes, final check and explicit refusals stay; SQL action abbreviations; index on relation columns; `indexed={...}` and index(); `foreignKeys=False` migration option; conversion of filled columns with backup; SQLite attach as legacy; index operator classes, first `text_pattern_ops` on `hierarchical_pkey` (moved from Macro 3); SQLite FK on by default and switchable; dtype SQL types as legacy; capability catalogue proposal (by theme, analytic capabilities); sqlglot transpilation as a documented proposal.
- Starts from: Macro 6.

## Macro 8: comparison document
- Objective: Sphinx chapter (English) and new team page (Italian) in the agreed form: Differences → Model / Query / Read-Write → missing (temporary, removed, replaced) / different / new / same, plus "to implement" as its own branch; cards "in GenroPy you wrote / got" above, asqueel below; one label; low-level vs high-level API; proposals (sqlglot, .sql(), capability catalogue, async).
- Starts from: Macros 2-7 landed.
