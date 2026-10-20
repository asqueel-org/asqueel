
## Phase 1

- Baseline was red (8 failed, 6 errors) before any edit: all `no such table` from asqueel-migration 0.3.0 attaching `<schema>.db` while asqueel attached `<stem>_<schema>.db`. The plan's Notes name this as the reason Phase 1 runs first; no `[x]` phase owns it, so the phase proceeded instead of blocking.
- `foreignKeys` on PostgreSQL is refused in two places: the builder's `driver` check (raised at construction, where `connection(options=...)` is normalised into `driver(...)`) and `PostgresAdapter.connect` (connect kwargs passed without the builder). Both messages name it as a SQLite connection option.
- `driver()` in `model_elements.py` and the driver check in `builder.py` were not in the plan's Files; the decision "the `driver` element gains it" needs both. `docs/grammar.md` is generated from the elements and was regenerated.
- Realignments outside the discovery rule, all from the legacy layout (every schema file lives in the main file's folder): `test_hosting.py` put four databases in one folder, now one folder each; `test_mounted_grammar.py` named the main file `chat.db`, which is now schema `chat`'s file, so the main file became `archive.db`; `test_wf_phase21_delivery.py` asserts the pin string; `docs/guide/migrations.md` stated the old pin.

## Phase 2

- Baseline: two full runs in the phase worktree stopped at the background time limit; the second hung in `test_python_errors_postgres.py` while source files were being edited under it (the migration module is imported lazily). A clean run on a detached worktree at HEAD gave 5221 passed / 27 xfailed, so the baseline was green.
- `verifyConversionBackups()` of asqueel-migration 0.3 deadlocks on PostgreSQL: the SELECT runs on the migrator's persistent connection (a transaction stays open) and `ALTER TABLE ... DROP COLUMN` runs on a new autocommit connection, which waits on the SELECT's lock. `migrate(backup=True)` closes the persistent connection and reopens it in autocommit before the call. To report to asqueel-migration; the workaround goes away with its fix.
- The object-tree path (`object_tree_relations.py`, `object_tree_projection.py`) already indexed every relation column and the non-pkey target (legacy `checkRelationIndex`), so it was not changed; only `object_tree.py` gained the `indexed={...}` reading. The renderer path (`migration.py`) was aligned to it.
- A target index is skipped also when a UNIQUE constraint covers exactly the target columns (legacy `fill_json_column_index` returns on a unique composite); `test_grammar.py::test_composite_target_resolves_to_its_member_columns` needs it.
- Weak relations (`x_weak`, no foreign key) add no index in the renderer: `model_source.py` already marks their columns `indexed`.
- Realignments: `test_legacy_model_query.py` used `onUpdate_sql='C'` as an invalid value, now `'X'`; `test_wf_phase20_strict_edges.py` no longer expects `indexed=False` refused on a `foreign_key=False` relation; `docs/grammar.md` regenerated.

## Phase 3

- Legacy facts cite genropy `origin/develop` at `5c72f3fbd7` (2026-10-19). `ADMINISTER` is declared in the enum but no adapter declares it and no code reads it; the catalogue keeps the name and leaves its scope to define.
- `allowAlterColumn` (legacy adapter class attribute, False on SQLite) is a capability outside the enum; the catalogue lists it under ALTER COLUMN and the declaration decision proposes folding it into the enum.
- The sqlglot proposal has one open decision (run the trial or not); the earlier SQLGlot trial is described without naming the internal design document, which is not part of the public xmldocs tree.

## Run inspection

- 3/3 phases closed `[x]`, no `[!]`, no repair, no budget cap tripped.
- Phase 2 session stood still 510 minutes (2026-10-19 22:32 → 2026-10-20 07:03 local) between two tool calls, then resumed and closed; the run's Monitor watches also expired silent in that window.
- Phase 2 baseline: two full-suite runs exceeded the 600 s Bash limit and went to background; the second hung in `test_python_errors_postgres.py` while sources were edited under it. The executor took the baseline from a clean detached worktree (5221 passed).
- Phase 2 `migrate(backup=True)` writes `migrator.db._connection` (a private attribute of asqueel-migration) to avoid the `verifyConversionBackups()` deadlock on PostgreSQL; the fix belongs in asqueel-migration. Focus point for the quality check.
- Phase 1 and Phase 2 touched files outside their `Files:` (`model_elements.py`, `builder.py`, `object_tree.py`, `docs/grammar.md`, realigned tests), each recorded in its notes.

## Final touch

Reviewed revision 752aa79 (review panel: one whole-diff reviewer, one migration specialist; QA: the Mermaid check of the sqlglot proposal run in the browser, diagram drawn, no syntax error). Correction commit a9456b6. Before it, asqueel-migration 0.3.1 was published (fix of the `verifyConversionBackups()` deadlock on PostgreSQL) so the private `migrator.db._connection` workaround could leave.

| # | Finding (evidence) | Root cause | Fix | Verification |
|---|---|---|---|---|
| 1 | Configured databases (AsqueelDb): a relation without foreign key indexed neither its column nor a non-pkey target; reproduced, no CREATE INDEX | `object_tree_relations.py` skipped on the column's own `indexed` (default False) | the relation's `indexed=False` is the only opt-out | tests/test_migration_legacy_paths.py |
| 2 | `migrate(backup=True, allow_removals=True)` with lost values: DDL committed, then MigrationError (re-check wanted to drop the kept backup column) | re-check with removals | re-check without removals when a backup column is kept | test_migration_legacy_paths.py (PostgreSQL) |
| 3 | `indexed={...}` options dropped silently under an explicit `index()` on the same columns | `setdefault` kept the explicit index | `_refuse_uncovered` raises when the options differ | test_migration_legacy_paths.py |
| 4 | Target index of a relation dropped silently under a partial explicit index | target loop had no refusal | same refusal as auto indexes | test_migration_legacy_paths.py |
| 5 | DDL error at apply surfaced as SqlMigrationError (CLI traceback) | only preparation was wrapped | apply and verification wrapped as MigrationError | test_migration_legacy_paths.py (PostgreSQL, NOT NULL on a NULL row) |
| 6 | Backup warning lost the verification error text | `report.get('lost_values', 'unverified')` | warning carries `report['error']` | review |
| 7 | Relation on a member of a composite pkey got an index; legacy skips any pkey member | comparison with the whole pkey only | skip a single pkey member on both paths | test_migration_legacy_paths.py |
| 8 | `SqlMigrationRenderer(foreign_keys=)` snake_case in public API | naming | `foreignKeys` | grep, suite |
| 9 | legacy-features.md A4.6 and A6.29/A8.18 stale | not rewritten in the phases | rewritten | read |
| 10 | Proposals described current asqueel (earlier sqlglot trial, listen/notify "rimandati", "l'errore già usato"); "capability analitiche" vague | team rule | passages removed or compared with GenroPy; xmldocs check and render | xmldocs check valid |
| 11 | Undocumented: shared `<schema>.db` files in one folder; `foreignKeys=False` keeps existing FKs; new CREATE INDEX on upgrade | docs | sqlite.md, migrations.md, legacy-features.md, release-notes.md | read |
| 12 | Markers `wf:phase-2:new` on `unknown_indexed_keys`, `indexed_attributes` | autonomous run | names kept (accept all), markers removed | grep empty |

Also: pin `asqueel-migration>=0.3.1,<0.4` (pyproject, migrations.md, test_wf_phase21_delivery.py); `_connection` workaround removed.
Checks run: full suite 5259 passed, 42 skipped, 27 xfailed; ruff and mypy clean; Light re-check over the batch: no findings. Rows on the phase road: none. Accepted risk: none.
