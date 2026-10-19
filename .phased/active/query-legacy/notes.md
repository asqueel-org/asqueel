
## Phase 1
- Cursors: `Database.cursor(query, cursorname=None)` runs through `_execute_on_connection`, so it shares the transaction state; the adapters gained `open_cursor` (PostgreSQL: psycopg named cursor when `cursorname` is given; SQLite ignores it and keeps `_begin` for `for_update`).
- `servercursor()` names its cursor `asqueel_<uuid>`; legacy passes `'*'` to its own generator of names.
- `iterfetch`/`serverfetch` yield NamedList chunks and stop at the first empty chunk (the contract expects `[2, 1]`; legacy also yields a trailing empty list). `cursor()`/`servercursor()` return the driver cursor with driver rows.
- `fetchAsBag` sorts by the key only; legacy `sorted()` on `(key, None, dict)` tuples gives the same order and fails on duplicate keys.
- The delete reread keeps the options of the removed `record()` (all physical columns, `exclude_draft=False`, `exclude_logical_deleted=False`, `ignore_partition=True`, `bagFields=True`) so its missing-row behaviour is unchanged.
- Stopped on a plan-defect claim about `fetchGrouped(ordered=True)`: see the phase Issue.
## Phase 1
- Plan-defect claim confirmed by the foreman: the contract test assumed `fetchGrouped(ordered=True)` sorts the keys; legacy keeps the fetch order. Line 84 corrected to `['y', 'x']` in both copies (run stopped on the user's answer, repair launched by the relaunch).

## Phase 2
- `environment_arguments(keys, snapshot)` lives in `environment.py`: `runtime.py` must not import `adapters` (tests/adapter_integration/test_boundaries.py); `prepare_arguments` and the runtime share it.
- `CompiledQuery.environment_keys` (and `SqlCompiledQuery.environment_keys`) carries the `:env_*` keys; `_execute_on_connection` rebuilds the params with the current values before the driver call. Explicit `env_*` caller parameters are not in the keys and are never overwritten.
- `refused_property(subject)` in `contracts.py` serves both the table refusals and `db.query`/`db.whereTranslator` (on `runtime.Database`).
- Tests outside the plan's list realigned by the same rule (a reused query no longer recompiles): test_postgres_policies, test_count, test_legacy_resolution, test_minimal_select, test_phase3_formulas, test_phase4_macros, test_phase4_star_bag, native_formulas/test_method_results and test_subquery_method_results; a scope that changes the SQL text (partition guards, #PERIOD dates, method formulas) builds a new query.
- Fake adapter of tests/application_connections/test_connections.py records `executed_params` so the env-at-execution realignments can assert the values sent.
