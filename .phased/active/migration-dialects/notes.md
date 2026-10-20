
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
