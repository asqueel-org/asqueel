# Context: plan/write-cycle
Parent: codex/core-release-0.6 | Issue: #30
Mode: autonomous
Theme: hierarchical tables
Must not break: the full suite (4903 passed, 42 skipped, 32 strict xfail on PostgreSQL and SQLite at 30efc91) stays green, apart from changes this plan states
Must not break: hierarchical triggers run only as field triggers inside the `db_write.py` cycle, through `SqlTable.query/update/delete`; no second write path. Macro 6 rewrites that cycle (delete reread through fetchRecord, query().update() through triggers, lock(), for_update modes) and hierarchical tables must follow it unchanged
Must not break: `options()` stays the declaration of sys_fields and hierarchical (user decision; Macro 4 keeps it)
Must not break: every refusal names the feature the user wrote (Macro 2): options not executed by this plan keep refusing the write by name; Macro 8 lists the missing features from them
Must not break: the `x_*` keys the core reads by name stay accepted until Macro 4 brings their legacy spelling; only the `x_legacy_on*` trigger keys leave in this plan
Must not break: `text_pattern_ops` on the `hierarchical_pkey` index is owed to Macro 7 (index operator classes); the index stays declared through `unique=True` here
Must not break: `batchUpdate` (#32) must add the legacy `_notUserChange` check to `trigger_setTSNow`/`trigger_setCurrentUser`, omitted here because no asqueel record can carry it yet

## Objective
A table declared with `options().sys_fields()` and `options().hierarchical(...)` is readable and writable on PostgreSQL and SQLite, with the same results as legacy GenroPy develop (95da66ee64, which already carries commit 3c581d9d26: cycles refused, deleted parents read). On top of the legacy, three improvements of doc 36 §10.2: a moved node takes the last position among its new siblings, the 1296th sibling is an explicit error, max + 1 of `_row_count` runs under a lock. Closes #29 and #30.

## Work Plan
- [x] **Phase 1**: sys_fields columns written by their legacy field triggers (#29)
  - Pattern reference: legacy `gnrpy/gnr/app/gnrdbo.py` `trigger_setTSNow` (line 990) and `trigger_setCurrentUser` (1013), read with `git -C /Users/gporcari/Sviluppo/Genropy/genropy show origin/develop:<path>`; asqueel `src/asqueel/table_triggers.py:TriggersMixin` for where table hooks live; `src/asqueel/table_crud.py:_doFieldTriggers` for how they are dispatched
  - Files: src/asqueel/model_expansion.py, src/asqueel/table_triggers.py, src/asqueel/model_source.py, src/asqueel/runtime.py, tests/option_tables_support.py (new, copied), tests/test_sys_fields_write.py (new, copied), tests/test_native_option_expansion.py, tests/object_tree/test_shared_option_fields.py, docs/guide/limitations.md, docs/guide/legacy-features.md
  - Decisions:
    - Every option expansion writes its column triggers under the column grammar names `onInserting`, `onUpdating`, `onUpdated`, `onInserted`, `onDeleted` (already accepted by `elements.py:column`), never `x_legacy_on*`. This applies to every option, not only sys_fields: options this plan does not execute keep refusing the write in `require_write_capabilities`, so their triggers never run.
    - `trigger_setTSNow(record, fldname, **kwargs)` on `TriggersMixin`: `datetime.now(timezone.utc)` for a `DHZ` column, naive `datetime.now()` otherwise. The legacy `__full_mod_ts` copy and the `_notUserChange` check are omitted (full_update stays refused; no record can carry `_notUserChange` before #32).
    - `trigger_setCurrentUser(record, fldname, **kwargs)`: `record[fldname] = self.db.currentUser`. `currentUser` is a new read-only property of the runtime db returning `self.currentEnv.get('user')` (legacy `gnrapp.py:537` without the page fallback).
    - `require_write_capabilities` stops refusing the `sys_fields` option, and the `id` column it declares (`read_only=True`, `x_generation={'type': 'uuid', 'algorithm': 'legacy22'}`): `checkPkey` already generates that key. `read_only`/`x_generation` on any other column keep refusing.
    - Existing tests asserting `x_legacy_onInserting`/`x_legacy_onUpdating` (test_native_option_expansion.py `assert_legacy_columns` and line ~406, test_shared_option_fields.py ~84) are realigned to the grammar names.
  - Details: rename the trigger keys in `model_expansion.py` (`_legacy(onX=...)` → plain `onX=`); add the two triggers and `currentUser`; narrow the write gate; copy `tests/phase-1/*` verbatim into `tests/`; realign the old tests; move #29 out of the limitations list in docs/guide.
  - Done: the plan's tests for this phase, copied into the test tree (`tests/option_tables_support.py`, `tests/test_sys_fields_write.py`), pass on SQLite and PostgreSQL; `venv/bin/python -m pytest -q` passes with only the 32 existing strict xfails; `venv/bin/ruff check src tests` and `venv/bin/python -m mypy src` clean; `grep -rn "x_legacy_on" src/asqueel` empty
  > Done: option triggers carry the grammar names; `trigger_setTSNow`, `trigger_setCurrentUser` and `db.currentUser` as legacy; the write gate executes sys_fields and its `id`; contract tests 9 passed on SQLite and PostgreSQL, copies byte-identical; suite 4912 passed, 42 skipped, 32 xfailed; ruff, mypy clean; x_legacy_on grep empty
  > Files: src/asqueel/model_expansion.py, src/asqueel/model_source.py, src/asqueel/runtime.py, src/asqueel/table_triggers.py, tests/option_tables_support.py, tests/test_sys_fields_write.py, tests/test_native_option_expansion.py, tests/object_tree/test_shared_option_fields.py, docs/guide/legacy-features.md, docs/guide/limitations.md
  > Review: closed by the foreman with /close-phase: the run's executor session ended while its full suite ran in background, leaving the work green but uncommitted; Done re-run in full before the close. `_legacy()` keeps the trigger keys by an allow-list (`_TRIGGER_KEYS`) instead of separate keyword arguments

- [x] **Phase 2**: hierarchical tables read and written as legacy develop (#30)
  - Pattern reference: legacy `gnrpy/gnr/sql/gnrsqltable_proxy/hierarchical.py` `HierarchicalHandler.trigger_before`/`trigger_after` and `gnrpy/gnr/app/gnrdbo.py` `trigger_hierarchical_before/after` (lines 753-757), legacy `gnrsqltable/table.py:82-83` (handler created when the table has `hierarchical`); asqueel `src/asqueel/table_crud.py:deleteRelated` for reading related rows without draft/deletion filters
  - Files: src/asqueel/hierarchical.py (new), src/asqueel/application_table.py, src/asqueel/table_triggers.py, src/asqueel/model_expansion.py, src/asqueel/model_source.py, pyproject.toml, tests/test_hierarchical_tables.py (new, copied), tests/test_native_option_expansion.py, docs/guide/limitations.md, docs/guide/legacy-features.md
  - Decisions:
    - Proxy as legacy: `HierarchicalHandler(tblobj)` in `src/asqueel/hierarchical.py`, created by `SqlTable` as `hierarchicalHandler` when the model has the hierarchical table attribute (today `x_legacy_hierarchical`, the comma list ending in `pkey`). `trigger_hierarchical_before(record, fldname, old_record=None, **kwargs)` and `trigger_hierarchical_after(...)` on `TriggersMixin` delegate to it. No dbo layer.
    - `trigger_before`/`trigger_after` are the legacy develop bodies: parent read with `excludeLogicalDeleted=False, excludeDraft=False`; a move under itself or a descendant raises `self.exception('business_logic', msg='A node cannot be moved under itself or one of its descendants')`; `_row_count` = max + 1 among siblings on insert when absent; paths `'%s/%s'`; `copyFromParent` columns copied; `_h_count` with `encode36(n, 2)`; `trigger_after` without old_record raises `self.exception('standard', msg='Updating a hierarchical record requires old_record')`; children rewritten one `update` at a time, read `for_update=True` without draft/deletion filters. `subtable='*'` has no asqueel counterpart and is dropped. `encode36` is written in the module (legacy `gnr/core/gnrstring.py:845`), with no other caller.
    - `child_count` formula becomes `select=dict(table=<self>, where='$parent_id=#THIS.id', columns='COUNT(*)')`: same count as the legacy `@_children.parent_id=#THIS.id`, without a path through the many relation. `assert_legacy_columns` skips `select` for `child_count` with a comment saying why.
    - `root_id` `sql_value` becomes `substr(:hierarchical_pkey,1,22)` (PostgreSQL and SQLite both have `substr`).
    - Write gate: `hierarchical` is executed; `auto_counter` passes only on a hierarchical table (there `_row_count` is assigned by `trigger_hierarchical_before`, no `setRowCounter`), and keeps refusing elsewhere (#31).
    - `hierarchical(linked_to=...)` and `hierarchical(depth=...)` raise `UnsupportedFeatureError` when the model is expanded, message `<table>: hierarchical linked_to is not available in this release` (and `depth`), doc 36 §10.4. `test_linked_hierarchy_and_legacy_variants` is rewritten to expect that error; `virtual_roots` and `root_id` keep working.
    - `pyproject.toml`: `asqueel-migration>=0.2.3,<0.3` in both the `migration` and `dev` extras (0.2.3 adds deferrable foreign keys on SQLite, needed by the deferred `parent_id` relation).
  - Details: write the handler and the two table triggers; change `child_count`, `root_id`, the gate and the deferred sub-options in the expansion; bump the pin; copy `tests/phase-2/*` verbatim into `tests/`; realign the expansion tests; move #30 out of the limitations list and document hierarchical tables in docs/guide/legacy-features.md.
  - Done: the plan's tests for this phase, copied into the test tree (`tests/test_hierarchical_tables.py`), pass on SQLite and PostgreSQL; the Phase 1 tests still pass; `venv/bin/python -m pytest -q` passes with only the existing strict xfails; ruff and mypy clean as in Phase 1
  > Done: `HierarchicalHandler` in `hierarchical.py` with the legacy develop `trigger_before`/`trigger_after` and `encode36`; `SqlTable.hierarchicalHandler` when the model has `x_legacy_hierarchical`; `trigger_hierarchical_before/after` on `TriggersMixin`; `child_count` on `$parent_id`, `root_id` with `substr`; the gate executes `hierarchical` and `auto_counter` on hierarchical tables; `linked_to`/`depth` raise at expansion (their dead expansion code removed); pin `asqueel-migration>=0.2.3,<0.3`. Contract tests 29 passed (13 on PostgreSQL), copy byte-identical; suite 4943 passed, 42 skipped, 32 xfailed; ruff, mypy clean
  > Files: src/asqueel/hierarchical.py, src/asqueel/application_table.py, src/asqueel/table_triggers.py, src/asqueel/model_expansion.py, src/asqueel/model_source.py, pyproject.toml, tests/test_hierarchical_tables.py, tests/test_native_option_expansion.py, tests/application_config/test_table_model_fallback.py, tests/test_wf_phase21_delivery.py, docs/guide/limitations.md, docs/guide/legacy-features.md
  > Review: two tests outside the plan's Files were realigned: `test_wf_phase21_delivery.py` asserted the 0.2.2 pin string; the `StructuralTable` fake of `test_table_model_fallback.py` gained `attributes = {}` because `SqlTable.__init__` now reads `model.attributes`

- [ ] **Phase 3**: sibling order beyond legacy — last position on move, bounded `_h_count`, locked max + 1
  - Pattern reference: the Phase 2 `HierarchicalHandler.trigger_before`; `src/asqueel/write_compiler.py:lock_table` for the table lock; `tests/sqlite/test_sqlite_application.py` (ThreadPoolExecutor) for a bounded concurrency test
  - Files: src/asqueel/hierarchical.py, tests/test_hierarchical_improvements.py (new, copied), docs/guide/legacy-features.md
  - Decisions:
    - On update, when `parent_id` changes and the table has `_row_count`, the node gets max + 1 among its new siblings (doc 36 §10.2); its `_h_count` and its subtree's follow through the legacy `trigger_after` cascade.
    - `_row_count` above 1295 (two base-36 digits) raises `self.exception('business_logic', msg='at most 1295 siblings under one parent')`, both when computed and when given; legacy `encode36` returns '' there.
    - Before max + 1, a child insert or move reads its parent row with `for_update=True`; a root insert or move to root executes `write_compiler.lock_table(model, snapshot, mode='SHARE ROW EXCLUSIVE')` on PostgreSQL (SQLite gets no statement; its writes are already serialized). Macro 6 replaces the direct call with the legacy `lock()`.
    - The concurrency test is a skeleton: its body is written in this phase, its `wf:contract:` lines are the contract.
  - Details: add the three behaviours to the handler; copy `tests/phase-3/*` into `tests/`; implement the skeleton body; document the three differences from legacy in docs/guide/legacy-features.md.
  - Done: the plan's tests for this phase, copied into the test tree (`tests/test_hierarchical_improvements.py`), pass on SQLite and PostgreSQL with the skeleton's `wf:contract:` lines verbatim and no `pytest.fail('phase 3 pending')` left; Phases 1-2 tests still pass; full suite, ruff and mypy as in Phase 1

## Notes
- Precondition of the run: asqueel-migration 0.2.3 published and installed in `venv/`. Its commit is 2c2f1b2 on branch `claude/modest-wilbur-f657a3` of the asqueel-migration repository; the user merges, tags and publishes it. Before that, every SQLite migration of a hierarchical table fails with `unsupported 'fk_deferrable'`.
- Run the full suite (about 8 minutes) as a foreground Bash call with `timeout: 600000`, never `run_in_background`: the Phase 1 executor session ended while waiting for a background suite, leaving its work uncommitted.
- Contract tests import `tests.option_tables_support`, a Phase 1 file reused by Phases 2-3; it is read-only from Phase 2 on.
- Moved to Macro 7: `text_pattern_ops` on the `hierarchical_pkey` index (no operator class in the index grammar, the migration, or the projection).
- Out of this plan (doc 36): LIKE escaping (the core generates no LIKE on paths here), the subtree/ancestors/root API (to be designed with virtualRelation), `getHierarchicalData`, `hierarchicalSearch`, `pathFromPkey`, `getAncestors`, `fixRowCount` (application-level), linked_to, depth.
- Adopted branch plan/write-cycle, worktree worktrees/write-cycle. No push. Commits carry no AI attribution.

## Suggested execution config
| Phase | Effort | Model |
|-------|--------|-------|
| Phase 1 | medium | opus |
| Phase 2 | high | opus |
| Phase 3 | medium | opus |
| Repair | high | opus |
