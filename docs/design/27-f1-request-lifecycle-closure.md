# 27 — F1: application-owned request lifecycle and recovery

1 October 2026. Completion evidence for the synchronous F1 profile in the working
tree after `022132b`. This does not certify complete Genropy application parity,
F0's entire inventory, multi-store or async support. F2–F10 acceptance stays open.

Structural correction: this report originally left the internal Session entity
in place and therefore did not complete F1. [Report 28](28-db-owned-connection-lifecycle.md)
records its removal and the repeated acceptance checks.

## Application boundary

Source review: `GnrWebPage.db` initializes the shared application DB's current
thread environment on first access, clears previous context and adds request
values. Subsequent accesses reuse it. Virtual pages can deliberately share the
parent page's DB context. `GnrWsgiSite.cleanup` closes the thread's connections.
Legacy revision: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.

The same ownership pattern is supported by existing Asqueel primitives:
application request object with a lazy `db` property; `clearCurrentEnv()` and
`updateEnv(...)` at request start; `closeConnection()` and environment cleanup
at request end, including failure. `closeConnection()` permits the shared DB to
be used for another request on the same thread. `close()` closes that thread's
DB state and is not the reusable request boundary.

Clearing environment is not transaction cleanup. An application must close or
roll back pending connections, including named ones, before reuse. Database now owns the connection lifecycle directly, using data records in its
thread-local named-connection dictionary. No Session container remains; see
report 28 and async portability record 26.

## Callback failure contract

Handled callback errors return normally and permit the next callback. An
escaping exception stops dispatch and reaches the application unchanged. A
successful SQL commit is already durable. There is no continue-on-error loop,
error aggregation or automatic callback retry.

The previous native after-commit handler additionally cleared both queues on a
Python exception. That cleanup policy has been removed: callbacks not reached
remain pending until the application rolls back/closes, or deliberately starts
and commits new work in the same context. A second commit without pending SQL
does not run them. This follows the clarified application-owned recovery model.
The failing callback has already been removed and is not rerun automatically.

If a callback opened new SQL work before failing, the existing failed-write
barrier remains: that work must be rolled back before reuse. SQL execution
failures still trigger the existing automatic rollback/queue cleanup. This is
not general permission to commit partial failed work. Request cleanup removes
remaining callbacks on every named connection before the next request.

## Remaining caller review completed for the F1 boundary

[Executable oracle](evidence/remaining_recovery_oracle.py) and
[results with source hashes](evidence/remaining_recovery_oracle.json): nine
scenarios per implementation run original caller AST methods on real isolated
PostgreSQL. Original core methods and the real legacy Bag use the existing
oracle. Mail/network, directory enumeration/XML, model lookup and record-context
helpers are fixture stubs. No message is sent and no extension is installed.
This verifies failure boundaries, not delivery of those application services.

| Contract | Observed result / destination |
|---|---|
| RC03 logger | Prior report 21 reproduces swallowed Python write failure without rollback. Adapter/application must rollback the failed logging transaction before the next log; core already supplies the primitive. |
| RC50 old IMAP helper | A caught Python attachment-write failure can be committed with the next message in legacy; native blocks continuation. A SQL failure rolls back before the next message in both. Adapt the helper to explicit rollback before continuing, or use the active importer already verified in report 21. External consumers remain unknown. |
| RC26 mail batch | The broad handler catches failure in the success-log write and tries an error-log write on the same system connection. Python hook failure blocks that fallback in native; legacy can save both partial success and error logs. Adapter must rollback the failed logging transaction before fallback, and distinguish successful external send from failed logging. SQL error path already rolls back in both. |
| RC51 SMTP queue | Queue removal is inside the SMTP catch scope and can be attempted twice. A caught Python write failure cannot be repaired by another write in native. Adapter must separate external send outcome from DB recovery, rollback failed DB work and reconcile the queue without blindly resending mail. SQL-error fixture paths recover in both. |
| RC18 extension DDL | Original addExtensions/createExtension methods catch a real unsupported-extension SQL failure. Core automatic rollback clears earlier pending work; a new operation succeeds on both. Migration/application code must isolate this operation from unrelated writes and report failure. Native extension management itself belongs to F9/F10. |
| RC45 directory visitor | A visitor's OSError can be swallowed by the directory-access handler after a write. Legacy may commit it; native rejects commit. Adapter must narrow the filesystem catch or rollback/report before continuing. SQL errors propagate in both. |

All nine scenarios verify that connection cleanup adds no commit and the next
request can initialize fresh context and write successfully. These dispositions
provide concrete contracts and use existing core primitives; no new core
recovery API or weakening of rollback protection is needed. Full mail/storage
integration, user applications outside the catalog and multi-store bulk/raw
fallback remain outside this F1 certification, explicitly assigned to their
application/adapter or later-phase work.

## Native acceptance

- `test_request_lifecycle.py`: ten real-backend cases, PostgreSQL/SQLite ×
  application/Python hook/SQL/precommit/postcommit failures. Same DB and thread,
  two consecutive request objects; environment, callbacks on main/auxiliary
  connections and pending writes do not leak. Previously committed data survives.
- `test_callback_recovery.py`: eight backend cases now include deliberate
  same-request continuation after a postcommit error with no new failed SQL.
- `test_deferred.py`: the no-forced-discard regression failed before the change;
  callback handling, stop-on-error and successful subsequent work are verified.
- Existing F1 tests cover thread isolation, independent named completion, false
  environment values, uncertain commit, cleanup errors, original error identity,
  trigger-stack restoration, deferred ordering/deduplication and SQL recovery.
- Date/locale profile remains the accepted context-only contract from report 24,
  without Babel or locale validation. Windows UI-language lookup is not ported.

The release remains 0.3.0 until a later explicit release. The changes here and
preceding local documentation/date-context work require a delivery commit; this
report is not evidence of a push or package publication.

Final validation: **650 tests passed**, **95% coverage**, on isolated PostgreSQL
and SQLite. Ruff and mypy pass for the changed code (mypy: 40 source files).
Sphinx validation uses warnings as errors. These were the original checks before structural correction; report 28 records
the repeated checks after Session removal. Record 26 captures future async work.

Reproduce the original-caller comparison with the existing legacy dependency
environment and a disposable PostgreSQL service:

```sh
PYTHONPATH=src:/path/to/legacy-dependencies python \
  docs/design/evidence/remaining_recovery_oracle.py \
  --legacy-root /path/to/genropy --dsn "$TEST_DSN" \
  --output /tmp/remaining-recovery.json
```

The oracle creates and drops only its uniquely named fixture schemas.
