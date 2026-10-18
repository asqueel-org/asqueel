## Phase 1
- Naming review: `trigger_setTSNow`, `trigger_setCurrentUser`, `currentUser` are legacy names (field-trigger dispatch and the legacy db property); no free part, accepted as is.
- The executor session of the run (opus/medium) ended after 16m43s waiting for a background suite run; the launcher stopped with "no progress". The foreman verified Done and closed the phase.

## Phase 2
- `linked_to` and `depth` raise in `_TableExpansion.hierarchy()` before any column is added; `_linked_hierarchy` and the `hdepth` variant block became unreachable and were removed, not kept as dormant code.
- The legacy `fieldsChanged` and `readColumns` have no asqueel counterpart: `hierarchical.py` compares the fields inline (`_changed`) and reads the max `_row_count` with `query(...).fetch()`; the root case passes no `p_id`, because asqueel refuses a keyword binding the query does not use.
- `trigger_after` reads the children with the physical column list (as `table_crud._related_rows`), so the row passed as `old_record` holds only physical columns.
- `HierarchicalHandler` keeps only `tblobj`: the legacy `self.db` has no reader here.
- The full suite runs in about 6.5 minutes with `--no-cov`; with coverage it took 11 minutes, beyond the 600 s foreground limit.

## Phase 3
- `next_position` in `trigger_before` covers both cases that compute max + 1 (insert without `_row_count`, move to another parent); the parent is read `for_update` only then, roots get `lock_roots()` only then.
- The 1295 bound is checked after the assignment, so it covers a computed and a given `_row_count`, on insert and update.
- The concurrency skeleton builds its two `AsqueelDb` instances inside the test body (the helper `migrated_db` creates one db only and `option_tables_support.py` is read-only); the second db sets `lock_timeout = '10s'` and every future wait has a timeout. With the parent at position 1 the two roots get 2 and 3.
- Closed `[!]` on a plan-defect claim about the 1296th-sibling contract test: a trigger exception leaves the connection rollback-only.

## Run inspection
- Three launches. Phase 1's executor session (opus/medium) and the first Phase 3 attempt ended while waiting for a full suite they had sent to the background: `addopts` adds `--cov`, which takes the suite to about 11 minutes, beyond the 600 s foreground limit. The launcher stopped on "no progress" both times. The foreman closed Phase 1 with /close-phase after re-running its Done; for Phase 3 the plan Notes were tightened (`--no-cov`, foreground) and the run relaunched.
- Phase 2 closed first time (opus/high), with two tests outside its Files realigned (`> Review:`).
- Phase 3 closed `[!]` on a plan-defect claim: the 1296th-sibling contract test assumed a connection stays usable after a trigger exception; asqueel marks it rollback-only. The foreman confirmed the premise in `runtime.py` `_write_operation`, the user chose apply, the declared edit went into both copies and the Done re-ran green (suite 4948 passed).
- `wf:phase-2:new` and `wf:phase-3:new` markers are still in `hierarchical.py` and `table_triggers.py`, waiting for the quality-check naming review.

## Final touch
- Reviewed revision: 320401c (review extended, effort high; QA none: the plan has no Verify steps).
- Naming: all seven markers accepted (`encode36`, `HierarchicalHandler`, `trigger_before`, `trigger_after`, `trigger_hierarchical_before`, `trigger_hierarchical_after` are legacy names; `lock_roots` has no legacy counterpart) and removed.
- 1. Partial update rewrote the node as a root with NULL paths (reproduced on SQLite) → `trigger_before`/`trigger_after` read absent keys from `old_record`.
- 2. Sibling max + 1 skipped logically deleted and draft siblings → filters off (doc 36 §10.2).
- 3. `auto_counter(field=...)` other than `_row_count` on a hierarchical table was accepted and ignored → raises at expansion.
- 4. Refused options were named in set order → declaration order.
- 5. The 1295 bound blocked updates of a stored overflowed row → checked only when `_row_count` is written (insert, computed, changed).
- 6. `_TRIGGER_KEYS` lacked `onDeleting` → added.
- Dismissed: the parent read on every child update (legacy behaviour, doc 36 §10.1).
- Tests: `tests/test_hierarchical_edge_cases.py` (new, 5 tests on rows 1-5); suite 4955 passed, 42 skipped, 32 xfailed; ruff, mypy clean. Rows on the phase road: none.
