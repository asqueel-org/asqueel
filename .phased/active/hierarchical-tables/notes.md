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
