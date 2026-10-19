
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

## Run inspection
- Phases 1-3 closed on the first session each (46m51s, 37m05s, 25m01s); no failure, no repair, no foreman consult.
- Phase 4 took three launches. The first two sessions (1m54s, 13m09s) started the full suite with `run_in_background`, wrote that they would resume on its notification, and ended: a headless `-p` session ends with its turn, the background suite died with it, and the launcher stopped on "no progress" (`run-end stopped 3/4`) with the phase still `[ ]` and the work uncommitted.
- First stop: the 2-minute leftover was discarded on the user's ok. Second stop: the leftover (contract tests 14/14 green) was committed as `wf(phase 4): partial` (222db0e) and Phase 4 got a run note (c94a255): full suite in the foreground, never in background. The third session verified and closed in 7m58s.
- Skill defect for the wf-lessons ledger: `/execute-phase-agent` lets a headless executor background the suite and wait for a notification that cannot arrive; the launcher reports it only as "no progress".
- Final suite at the Phase 4 close: 5194 passed, 42 skipped, 27 xfailed; ruff and mypy clean.

## Final touch
Reviewed revision 3480fad (panel: one whole-diff reviewer + one transactions specialist, both opus; QA none — the plan carries no Verify steps). Naming: all 32 new names kept (user, 2026-10-19: words of our language follow the GenroPy rule, internal code the Python idiom; a team glossary will settle final names); markers removed. Correction commit a819623.

| # | Finding | Root cause | Fix |
|---|---|---|---|
| 1 | an unread SqlCursor kept the SQLite file locked after closeConnection/session exit | cursors outlived their connection | state records open cursors (WeakSet); `_close_connection` closes them first |
| 2 | fetch error on a stale cursor cleared the new transaction's deferred queue and pending exceptions | same | `_fetch` rolls back only when the cursor's state and driver connection are still current |
| 3 | `_pendingExceptions` shared by every named connection | one global key against the Phase 1 decision ("of their connection") | `_pendingExceptions_<connectionKey>`; guide states the difference from legacy |
| 4 | `query().delete()` raised RecordNotFoundError on rows already removed by a cascade | delete of a complete dict requires the row | the terminal deletes by pkey string (reread, missing → skipped), as legacy deleteSelection |
| 5 | composite keys with I/DHZ/B members did not round-trip (read `"5::I"`, decoder knew D/DH/H/N) | decoder narrower than the composite formula | every legacy typed suffix decoded; B member 1/0 accepted |
| 6 | vacuum with pending work: SQLite locked 20 s, PostgreSQL VACUUM FULL hung | separate connection waits on the open transaction (legacy too) | TransactionStateError when the thread has pending work |
| 7 | insert assigned max+1 to a pkey with sql_default, sql_insert did not | rule only in sql_insert | one rule `_pkey_from_database` used by checkPkey and sql_insert |
| 8 | session(db): cleanup error replaced the body's; read-only SqlEnvironment gave AttributeError | no handling | note on the body's error; explicit TransactionStateError |
| 9 | stale docs and dead code (api.rst, oracles, cli banner, QueryResult in two docs, hierarchical lock_roots None check), SqlCursor not exported | Phase 1-3 leftovers | updated; SqlCursor exported; docs/adattamenti-legacy.md paragraph on insert rewritten to the current behaviour |
| 10 | 32 `wf:phase-N:new` markers; Macro 7 note on vacuum with SQLite attach | — | markers removed; roadmap Macro 7 line extended |

Checks run: full suite 5213 passed, 42 skipped, 27 xfailed (foreground); ruff clean; mypy clean; marker grep empty; contract tests phase-1/3/4 byte-identical, phase-2 differs only by its two implemented skeletons. Re-check: light review (opus, low) over a819623 — one judgment: `query().delete()` passes a text key for integer/date pkeys and no test covers it; reproduced on SQLite and PostgreSQL with dtype L and D pkeys, both delete correctly → dismissed with evidence, no residual defect. Rows on the phase road: none.
