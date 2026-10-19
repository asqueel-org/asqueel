
## Phase 1
- Snapshots: ApplicationEnvironment.current_env deep-copies currentEnv for every compile/execute; the deferred Bags hold callbacks (bound methods) that deepcopy can copy or fail on, so environment.py excludes `to|after_commit_defer_calls_*` and `_pendingExceptions` from snapshots. environment.py was not in the phase Files.
- Read-only environments: a Database built with `environment=SqlEnvironment(...)` has a MappingProxy currentEnv. `_pop_transaction_key` pops only from a dict; nothing can be queued there, so rollback/commit stay working. deferToCommit on such a database fails (no mutable env), as updateEnv already did.
- Hosting: the same database taken through two owners in one call (test_names_with_a_colon_belong_to_an_application) would open a nested session. `_take` enters session(db) only when the database has no open session on the thread; the other owner records the take without a session and its release leaves it alone.
- `_finish`: the `outcome` field is gone; an uncertain commit is a local flag that still clears the deferred queues. The not-pending branch resets `failed` unconditionally (the old `outcome != 'unknown'` guard was unreachable behind `_check_connection_usable`).
- Realignment deleted tests whose subject no longer exists: test_tree_terminals.py::test_closed_query_fails_before_driver; test_python_errors.py::test_db_context_preserves_hook_exception_when_cleanup_also_fails[rollback|close], ::test_successful_db_context_still_reports_cleanup_failure.

## Phase 2
- Cursor class name `SqlCursor` (runtime.py), a proposal for the naming review. It holds the database and the connection state so a fetch error reuses the execute rollback (`_execution_failed`, extracted from `_execute_on_connection`).
- Result-name checks (unique names, compiled columns matching the cursor) moved from `adapters/base.query_result` into `SqlCursor.__init__`, still inside the execute try: a mismatch rolls back as before. `ResultColumn` stays because `CompiledQuery.columns` and the compiler use it.
- Adapter interface: `cursor(connection, cursorname=None)`, `execute(connection, query, cursorname=None)` and `executemany` return the driver cursor; `open_cursor` removed. Fake adapters in tests return `tests/unit_of_work.FakeCursor`.
- Maintenance calls live on the adapter as legacy (`analyze`, `setConstraintsDeferred` through `dbroot.execute`; `vacuum` on its own connection from `dbroot._connection_settings()`), the database delegates. `setLocale` is one no-op in the base adapter, inherited by both.
- Contract skeleton for the fetch error uses `fetchall()`: sqlite3 prefetches the next row, so the second row fails at the first `fetchone()`.
- `cursorname='*'` generates `'c' + uuid4().hex` (legacy: `'c' + uuid with \W → _`).
