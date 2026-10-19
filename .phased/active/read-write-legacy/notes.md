
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

## Phase 3
- `toTypedJSON`/`fromTypedJSON`/`JSONTypedEncoder` live in write_compiler.py: the write compiler parses keys (`key_values`), table_crud imports the encoder. Decoding converts list members ending in `::D`, `::DH`, `::H`, `::N`, as legacy typedTextDeepConverter does for these suffixes.
- `key_values(table, pkey)` is public on WriteCompiler because `SqlTable._key_selector` uses it too (one parser for update, delete, reread, insertOrUpdate).
- SQLite `lock()`: a zero-row `UPDATE` of the first key column; sqlite3 in DEFERRED mode opens the transaction before DML, and the UPDATE takes the RESERVED lock. It is the statement `_begin` already runs for a for_update query inside a transaction.
- `insertOrUpdate` reads with `columns='*'` and `for_update=True` (which also brings the X columns), default filters on, as legacy.
- `for_update` validation: `0`/`1` ints refused like before (`type(...) is int`).
- Realigned: test_handles `test_hooked_delete_rejects_missing_or_multiple_records_before_hooks` → `test_hooked_delete_of_a_key_rereads_it_before_hooks` (the incomplete-dict reread it covered is removed by decision); test_write_cycle reread test now deletes by key string; test_write_compiler composite key as serialized string and SQLite lock statement.

## Phase 4
- `SqlQuery.update`/`delete` share `_rows_to_write(terminal)`: the query's options with every physical column, `bagFields=True` and `for_update` (a user mode `'NOWAIT'`/`'SKIP LOCKED'` is kept), rows as dicts after handleBagColumns. `group_by`/`having` raise naming the terminal.
- `update` returns `record[pkey]`; on a composite-key table the composite is not a physical column, so the key comes from `pkeyValue` (the serialized composite key).
- The cascade lives in `TableCrud.archiveRelatedRecords(record, archive_ts)` (legacy name; `onArchivingRecord` not added), called by `db_write.update` right after `_protect_draft`, the legacy `dbo_onUpdating` position. The change test is `record.get(ldf) != old_record.get(ldf)`, as legacy `fieldsChanged`.
