
## Phase 2
- Observation, psycopg 3.3.6: `execute("SELECT 'a%'", {})` raises ProgrammingError (only `%s`, `%b`, `%t` placeholders); with `None` it returns `a%`. `execute("SELECT 'a%%'", {})` returns `a%`; with `None` it returns `a%%`. `SqlDbAdapter._params` (`adapters/base.py:183`) always passes a dict, and every statement path goes through it (`execute`, `executemany`); `vacuum` executes unprepared text on its own connection. So doubling always is consistent and the empty-parameter path needs no change.
- Helper: `substitute_parameters_and_text(sql, replace, replace_text, dialect)` added to `_sql_parameters.py`; `substitute_parameters` left untouched (the mysql/mssql branches edit this file).
- Existing tests changed because they certified the protocol asqueel#19 reverses (the author doubled `%` by hand on PostgreSQL):
  - `tests/adapter_driver/test_legacy_preparation.py`: oracle records `prepared:postgres:percent` and `percent_bound` carry legacy `%%` in their input; expected output now has it doubled again (override, like the existing #35 override).
  - `tests/adapter_integration/test_boundaries.py`: a quoted identifier containing `%` comes out with `%%`; the compiled table name `"50%"` comes out as `"50%%"`.
  - `tests/adapter_integration/test_legacy_preparation.py::test_driver_percent_protocol`: PostgreSQL now takes the same single-`%` SQL as SQLite.
  - `tests/adapter_integration/test_postgres_pipeline.py::test_explicit_pipeline`: column `'50%'` written once, compiled as `'50%%'`.
  - `tests/application_integration/test_write_lifecycle.py::test_direct_sql_uses_driver_binding_and_same_environment`: one literal for both dialects.
- Phase 6: release notes must say that application SQL writing `%%` on PostgreSQL now produces `%%`.

## Phase 3
- Named sessions of one call share one dict (`_call_sessions`); the ContextVar holds the current SessionDb, and the first session of a call anchors it. `session(name)` reuses an open session of that name; `env` given to an already open session raises TransactionStateError.
- `virtual_columns` resolves the session through the ContextVar (current SessionDb of the call), since the property has no compiler argument: a SessionDb used as `with` body, or in its write cycle, is the one whose env and table methods `formulaColumn_*` use.
- Compiler `sql_formula_*`, `env_*`, `subquery_*`: `_TreeContext.dbtable(table)` returns `db.table(fullname)` of the compiling database.
- `:memory:`: the shared AsqueelDb opens the connection once; `_discard_connection` never closes it; `AsqueelDb.close()` does.
- `reloadModel` on a SessionDb delegates to the shared one, which checks every open session idle and clears their tables, compilers and virtual-column caches.
- `AsqueelDb.close()` closes every open session and continues after a failure, raising the first error with notes (the per-session equivalent of `closeConnection` cleaning every named connection after one failure).
- Rewrite of `tests/application_connections`: every `AsqueelDb(...)`/`empty_database(...)` builder takes `.session()`; the per-thread and `tempEnv(connectionName=...)` assertions map as follows (routing by `tempEnv(connectionName=...)` is Phase 4):
  - `test_thread_connections.py::test_simultaneous_threads_isolate_names_environment_hooks_and_completion` → `test_simultaneous_calls_isolate_names_environment_hooks_and_completion`: two calls (`contextvars.Context().run`) with a main and an `other` session each; 4 distinct states and sessions, callbacks, persisted rows, connect/close counts, shared env and trigger unchanged.
  - `test_named_environment_changes_selection_without_completion` → `test_named_session_changes_selection_without_completion`: `db.session('other')` instead of `tempEnv(connectionName='other')`.
  - `test_internal_connection_rejects_cross_thread_use` → `test_internal_connection_is_usable_from_another_thread_of_the_call`: the owner thread check no longer exists; concurrent use is refused by the executing flag (`test_session_db.py::test_concurrent_use_of_one_session_is_refused`).
  - `test_new_thread_does_not_inherit_environment` → `test_new_call_does_not_inherit_environment`.
  - `test_connections.py::test_connection_record_ownership_and_repeated_close_connection` → `test_connection_record_is_usable_from_another_thread_of_the_call_and_close_repeats`.
  - `test_locale_workdate.py::test_dates_and_locales_are_isolated_between_live_threads` → `..._between_live_calls`.
  - `test_named_connections.py`: named transactions, SQL error retry → named sessions; `test_close_connection_cleans_every_named_connection_after_one_failure` → `test_closing_the_database_closes_every_session_after_one_failure`; `test_close_connection_releases_all_names_and_database_can_reopen` → `test_closing_the_database_releases_every_session_and_a_new_one_reopens`. The fake adapter is per session, so `persisted` is asserted per session.
  - `test_deferred.py` (named queues, callback environment, trigger finishing another name) and `test_python_errors.py` (errors on B/C): `self.db.session('B')` etc. instead of `tempEnv(connectionName=...)`.

## Phase 4
- `tempEnv(connectionName='x')` routes at the connection-state level: `SessionDb._connection_state` returns the state of the call's session `x` (`_routed`), and `currentConnectionName` reports `x`, as legacy. The environment, trigger stack and adapter stay those of the calling session, so values set by the same `tempEnv` reach the statements, as with the single legacy env. Rejected: delegating whole operations to session `x`, which would run them with `x`'s env and drop the caller's `tempEnv` values.
- `_ConnectionState` gained `session`, the `SessionDb` that owns it. Deferred queues and pending exceptions live in the `currentEnv` of that session, and the connection opens with its `target`, so `x.commit()` runs callbacks registered through the routing and `x.close()` sees them. `SqlCursor._fetch` checks the owner's `_connections`.
- `_pop_transaction_key(state, queue)` replaces `_pop_transaction_key(key)` (private, used only in `application.py`).
- Hosting: the owner keeps, in a ContextVar attribute of its own, the list of sessions taken in the call and whether it opened each; a session already open in the call through another owner is used as it is and not closed by this owner. `taken_databases` now lists `SessionDb` instances.
- `test_hosting.py::test_each_thread_releases_only_its_own_takes` → `test_each_call_releases_only_its_own_takes` (`contextvars.Context().run`). The failure test patches `close` on the taken session instead of `closeConnection` on the shared db.
- `runtime.TransactionStateError` stays importable (explicit re-export): three test files import it from there.
- `test_request_lifecycle.py`: `Request.cleanup` closes the `auxiliary` session's connection too; the certified behaviour (the next request inherits no pending work) is unchanged.

## Phase 5
- Fixture shape: `AsqueelDb(...).session()`; teardown keeps an existing `closeConnection()`/`rollback()` and adds `db.shared.close()`. Helpers (`option_tables_support`, `query_completion_support`, `tree_execution_support`) close only the shared db: a test may close its session itself, and `closeConnection()` on a closed session raises.
- Body changes (assertions kept unless stated):
  - `tests/sqlite/test_memory_migration.py::test_secondary_connections_cannot_be_migrated_or_reloaded`: a `:memory:` db lends one connection to one session, so a secondary connection no longer exists; migrate/execute/`db.session('secondary')` now raise TransactionStateError 'one session at a time', `reloadModel` succeeds, the plan is empty.
  - `tests/sqlite/test_sqlite_application.py::test_threads_and_named_connections_use_same_files_with_independent_state`: the worker thread opens `with db.shared.session() as session:`.
  - `tests/environment/test_runtime_environment.py::test_runtime_aliases_use_current_context_on_the_calling_thread`: `db.shared.close()` after the last assertion.
  - `tests/test_connection_lifecycle.py`: `test_the_connection_api_has_no_close_with_acquire_or_outcome` → `test_the_connection_api_has_no_acquire_or_outcome_and_only_a_session_is_a_context_manager`; `test_session_clears_the_environment_and_applies_the_initial_values` asserts a new session does not inherit the previous env; the two session-exit tests verify in a new session; `test_a_nested_session_on_the_same_thread_raises` → `test_a_nested_session_of_the_same_call_is_the_open_one_and_refuses_new_values`.
  - `tests/test_release_connections.py::test_named_runtime_connections_reach_distinct_sqlite_databases`: opens `database.session('reporting', target='reporting')` before `tempEnv(connectionName='reporting')` (name and target are separate).
  - `tests/test_standalone_behaviors.py` (`test_concurrent_allocations_serialize`, `test_concurrent_opposing_moves_cannot_create_cycle`), `tests/native_runtime/test_runtime.py::test_close_connection_discards_pending_work_and_closes_only_current_thread`, `tests/application_integration/test_postgres_application.py::test_shared_database_threads_have_independent_postgres_connections`: each worker opens its own session (`contextvars.Context().run` where the worker is a call).
  - `tests/test_read_write_final_touch.py` cleanup tests: the failure is injected on `opened.adapter.close` instead of `db.closeConnection`.
  - `tests/test_model_cleanup_database.py::test_model_and_table_take_their_owner_only` and `tests/object_tree/test_operational_tables.py::test_creation_precedes_children_and_does_not_load_relations`: `SqlTable.__init__(self, tblobj, db)` (Phase 3 design).
- src: `SessionDb.__exit__` on a body exception closes without warning and adds `Connection cleanup failed: <Type>` to the body error instead of replacing it (the pre-Phase-4 `runtime.session` behaviour certified by `test_session_keeps_the_body_error_when_cleanup_also_fails`).
- src: `AsqueelDb._session_class` — `SessionDb` for a plain `AsqueelDb`, else `type(name, (SessionDb, type(shared)), {})` built once per shared db, so an application subclass's `execute`, write hooks and helpers run on its sessions (`test_write_lifecycle`, `test_raw_writes::SharedHooks`, `test_cli::ApplicationDb`). Rejected: rewriting those tests on another base, which would drop the certified subclass behaviour.
- pgbouncer contract file: module constant `QUERY` and helper `pgbouncer_db()` added next to the bodies; the skip for an unset `GNR_TEST_PGBOUNCER_DSN` lives in `tests/conftest.py::pytest_collection_modifyitems`. The named-cursor read after commit raises `psycopg.errors.InvalidCursorName` (checked against the local PostgreSQL).

## Phase 6
- `tempEnv(connectionName=...)` no longer reaches a configured connection of the same name (it opens the session with `target='main'`): `cli.md` and `configuration.md` now open a declared connection with `db.session('reporting', target='reporting')`.
- `:memory:` documented from observed behaviour, not from the design: without `migrate()` the lent connection keeps data across `closeConnection()` and session close until `AsqueelDb.close()`; with `migrate()` the data lives on the session's own connection and is lost when it closes. `migrations.md` examples use `.session()` and end with `db.close()`.
- The close warning paragraph states that a read-only session logs it too (a read opens a transaction), as observed in Phase 5.
- Executing examples that ran statements on the shared `AsqueelDb` (README, cheatsheet, cli, configuration read/write, environment request pattern, low-level-runtime, migrations) moved to `shared.session()`; compile-only examples on the shared db kept.
- Release notes list #19 and #24 too, since 0.9.0 ships them.


## Run inspection
- uneventful run, 6/6 phases: no [!], no repair, no budget cap tripped, no consult
- Focus points for the quality check, raised in the phase notes:
  - Phase 5/6: a read-only `with db.session()` logs the "closed with uncommitted work" warning (one SELECT marks the connection pending); Phase 6 documented it as observed instead of fixing it
  - Phase 5/6: SQLite `:memory:` + `migrate()` runs on the session's own connection, not the lent one: migrated tables are lost when the session closes (documented as is; `migration.py` frozen by Must not break)
  - Phase 3: `virtual_columns` finds the compiling session through the ContextVar: a named session compiling outside `with` and outside its write cycle uses the env of the current session of the call
  - Phase 4: the hosting owner keeps the call's sessions in a ContextVar of its own (asqueel#56 point 5 names one ContextVar holding only the current SessionDb)
  - Phase 5: sessions of an `AsqueelDb` subclass are built from a derived class `(SessionDb, type(shared))`
  - Phase 4/6: `tempEnv(connectionName='x')` opens session `x` with `target='main'`; a configured connection of the same name needs `db.session('x', target='x')`
  - Phase 6: Italian design docs under `docs/*.md` still describe per-thread state (outside the plan's Files)

## Final touch
- Reviewed revision: 0ce72ea (REVIEW_HEAD). Review: panel — one whole-diff reviewer + one concurrency/lifecycle specialist, both opus, read-only, reproductions under the session scratchpad. QA: none (no Verify steps, no verify.md).
- Correction commits: 1e99869 (`wf: final touch — 10 corrections`), 9833198 (`wf: final touch — +6`, residuals of the Light re-check).
- Checks run after each: ruff on src and tests; SQLite suite 4107 passed / 39 skipped / 12 xfailed; PostgreSQL suite 1407 passed / 6 skipped / 6 xfailed; `sphinx -E -W` clean; `wf:phase-N:new` sweep empty.

| # | Finding (evidence) | Root cause | Fix | Road / outcome |
|---|---|---|---|---|
| A | a reused worker's next call got the previous call's named sessions (s4, repro2); a named session opened first stayed current | `session()` reused the closed main's `_call_sessions` | new dict when the current session is absent or closed; main becomes current when created; routed sessions close with their opener | fixed |
| B | concurrent use not refused, leaked connection; `:memory:` lent twice; WeakSet iteration error at `AsqueelDb.close()` (s6, s7, s10) | check-then-act without lock | `state['lock']` around check+claim; `shared._lock` around registry and lend | fixed |
| C | refused close marked the session closed (s5) | state changed before the check | claim all states (own + routed) before any change; `AsqueelDb.close()` keeps `:memory:` when a session refuses | fixed; shared "closed" flag dropped: `tests/application_connections/test_named_connections.py` certifies reopen after `AsqueelDb.close()` |
| D | `:memory:` abandoned work committed by next session (s3); migrated tables lost (s1_s2, repro3) | no rollback on lend; migration on a private connection | rollback on lend; `SessionDb.migrate/migration_plan` use the lent connection (`migration.py` untouched) | fixed; `test_memory_migration.py` end aligned to contract point 9 |
| E | formulaColumn_* computed with another session's env (s8); shared env writes ignored by sessions (repro4) | ContextVar not set while compiling | compiler `plan_select/plan_count` and `WriteCompiler.prepare_record_data` make the compiling session current | fixed for sessions; shared env stays writable: it is read by the shared db's own compiler (350+ compile-only tests) — dismissed with that evidence |
| F | `tempEnv(connectionName='reporting')` read `main` (repro1), regression vs ad66132; vacuum on wrong target | `_routed` opened with target main | `target=name`; settings and vacuum follow the routed session without opening it | fixed; Phase 5 workaround line removed from `test_release_connections.py` |
| G | read-only session logged the uncommitted-work warning (s9) | every statement set pending | `state['wrote']` for non-read statements (`_reads_only`) | fixed |
| H | a fetch ran concurrently with a commit | fetch outside the `executing` flag | fetch claims the connection | fixed |
| I | dead state on shared; 9 `wf:phase-N:new` markers | — | markers removed (names accepted as proposed) | markers fixed; `_connections`/`_trigger_stack` kept on shared: same compile-only use as E — dismissed |
| J | Italian design docs and transactions.md described per-thread isolation | — | sentences updated | fixed |
| K | subclass `__init__` state missing on sessions (repro4) | session class does not run the subclass `__init__` | documented: keep instance state on the shared db, reach it as `session.shared` | user decision, documented |
| L | asyncio tasks share the session of their creating context | ContextVar copy at `create_task` | documented: one session per task | user decision, documented |
| R1 | close of an opener not refused by a busy routed session | pre-check covered own states only | claim routed states too | fixed (+6) |
| R2 | commit/rollback could overlap an execute of another thread | `_finish` set `executing` without check | `_finish` claims under the lock | fixed (+6); race window, test is a behavioural guard |
| R3 | statement could start between close check and claim | two separate steps | close claims every state atomically before releasing | fixed (+6); race window, test is a behavioural guard |
| R4 | vacuum under routing ignored the caller's pending work and opened the routed session | check on routed state only | check caller and open routed sessions, open nothing | fixed (+6) |
| R5 | data-modifying WITH and assigning PRAGMA counted as reads | `_READ_STATEMENT` too broad | `_reads_only` | fixed (+6) |
| R6 | release dropped tracking on failure; named sessions not closed when the app closed main | tracking removed first; call reached only via open main | track until closed; reach the call through the current session | fixed (+6); `test_hosting.py` failure test updated to the retry rule |

- Rows on the phase road: none. Accepted risk: none.
- Deviation from the approved table: E (shared env read-only) and I (dead shared state) were applied, broke 350+ compile-only tests that legitimately use the shared db's own environment and `closeConnection()`, and were reverted.
