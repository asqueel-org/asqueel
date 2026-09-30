# 20 — Python failures in hooks and deferred callbacks

30 September 2026. F1 investigation from Asqueel `e8e9bf4`; legacy baseline
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. **F1 remains open.** The native
rollback-only policy is verified below, but is not declared equivalent to the
legacy or accepted as a deliberate compatibility difference.

## Normal saves reject errors: clarification after checking the callers

The statement that “legacy permits saving with an error” is too broad. In the
normal `saveRecordCluster()` path, `onSaving`, record writes and `onSaved` must
finish before the handler calls `db.commit()`. An exception propagating from
these steps skips that call. Site cleanup invokes `closeConnection()`, which
rolls back pending work. `deferredRaise()` is a further commit barrier: pending
exceptions also prevent an explicit retry from succeeding.

The [save-handler oracle](evidence/legacy_save_error_oracle.py) and its
[results](evidence/legacy_save_error_oracle.json) execute the original
`saveRecordCluster()` and site `cleanup()` bodies against the PostgreSQL fixture.
All five failure cases (`onSaving`, before/after insert hook, `onSaved`, queued
`deferredRaise`) persist no changes after cleanup. The success control commits.
The queued-error case additionally verifies that explicit commit retry fails.

Permissions, page storage and the record-cluster-to-single-insert bridge are
fixture stubs. The existing core oracle supplies the original write/transaction
methods and the real Bag. The generic exception class used by its AST namespace
stands in for `GnrException` in the queued-error test; exception formatting is
not tested. This is a handler/cleanup execution test, not a full HTTP request.

The native rollback-only marker therefore adds a guard at the low-level API;
it is not evidence that ordinary legacy saves persisted failed operations.
Do not request approval of a broad behavioral change based on that mistaken
framing. The [caller follow-up](21-recovery-callers.md) now verifies explicit
rollback/recovery and independent logging paths, and identifies a concrete
logger missing rollback. Residual deferred queues and the caller-specific
boundaries listed there remain open; the native policy has not changed.

## Observable difference in explicit low-level recovery

A caller catches `ValueError` raised by an after-insert hook. The hook already
inserted an audit row; the primary INSERT has also executed.

- Legacy standalone core: a subsequent `commit()` persists both rows, plus any
  earlier work on the same connection. Remaining deferred callbacks run.
- Current Asqueel: `commit()` raises `TransactionStateError`. The caller must
  roll back, discarding the rows and queued callbacks, before starting new work.

Neither implementation makes these uncommitted rows visible to another
connection before commit. Both discard them when the caller explicitly rolls
back. The difference concerns whether a caller can continue after catching the
Python exception. It must be decided before asserting compatibility.

## Evidence and boundaries

The [executable oracle](evidence/python_error_oracle.py) records **16 scenarios
per implementation** against a disposable PostgreSQL database. The
[recorded results](evidence/python_error_oracle.json) include hashes of every
extracted legacy module and the original Bag. Each case uses its own schema,
a separate observer connection and cleanup after the experiment.

The oracle executes unchanged AST definitions of `EnvMixin`, `ConnectionMixin`,
`ExecuteMixin`, `TransactionMixin`, `WriteMixin`, `TempEnv`, `in_triggerstack`
and the trigger-stack classes. The real legacy Bag manages the deferred queues.
A small adapter executes fixture INSERT/UPDATE/DELETE SQL through the original
legacy `execute()` method. It does not use the legacy model/compiler or its
production adapter. Table validation, field/package triggers, counters, related
writes, SQL auditing and application notifications are excluded explicitly.
The native side uses public table writes, callbacks, commit and rollback.

This evidence covers the standalone lifecycle. It does not establish how every
Genropy caller handles exceptions. In particular, the inspected web path
`gnrwebpage.py::_rpcDispatcher` catches request errors; `gnrwsgisite.py::cleanup`
calls `closeConnection()`, whose legacy implementation rolls back and closes
connections. The follow-up above exercises the original save and cleanup handlers, but still
does not constitute an executed HTTP request. Deliberately catching an exception
and choosing to commit is a separate scenario.

## F0 contract register for this slice

| ID / family | Scenario and legacy result | Native result / disposition |
|---|---|---|
| PY01 / LT27, LT29 | Python failure in before/after insert, update or delete does not force rollback. Explicit commit can persist preceding and hook writes; after-hook failure also leaves the primary write pending. | Rollback-only. Six hook positions tested with both explicit rollback and attempted commit. Compatibility decision pending. |
| PY02 / LT28 | Pre-commit callback is removed before invocation. If it raises, a later commit drains remaining callbacks and can persist the partial work. | Retry is blocked until rollback; rollback clears queues. Tested with and without SQL inside the callback. Compatibility decision pending. |
| PY03 / LT28 | Post-commit failure leaves the first commit durable. If it opened new work, a retry can commit that work and run remaining callbacks. | First commit stays durable; new work becomes rollback-only and residual callbacks are discarded. Compatibility decision pending for retry behavior. |
| PY04 / LT28 | A post-commit callback that fails without new SQL can leave later callbacks queued until a future transaction commits. | Residual callbacks are discarded. Previously implemented difference, now demonstrated; not silently declared equivalent. |
| PY05 / LT29 | Original trigger-stack decorator does not pop after a raised hook exception (depth remains 1 in these isolated cases). | Stack returns to depth 0. Existing native cleanup guarantee retained; the legacy stack leak is recorded, not reproduced. |
| PY06 / LT26–LT29 | Cross-connection propagation and error replacement during cleanup are not certified by this legacy oracle. | Native regressions prove that an incomplete outer write cannot commit after another connection's SQL failure, independent connections remain usable, and cleanup cannot replace the original Python exception. |

F0 remains open outside this slice. The 42 LT families are an index, not a claim
that every variant has been enumerated. Locale behavior, application events,
full field/package trigger pipelines, raw/bulk writes, counters, related-record
cascades, and all external consumers still need their own evidence.

## Native defects corrected without changing the policy choice

1. **Wrong session credited with rollback.** `_write_operation()` accepted an
   execution error found in *any* named session as proof that its own operation
   had been rolled back. If a hook on A failed through SQL on B, A could still
   commit an incomplete write and publish its after-commit callbacks. Error
   attribution now requires an execution attempt in the operation's own session.
   B's automatic SQL rollback remains recoverable; unrelated C can still commit.
2. **An old exception mistaken for a current SQL rollback.** Reusing the same
   exception instance in a later Python hook could evade the failure marker.
   The session's execution counter distinguishes attempts made during this
   operation from stale exception identity.
3. **Cleanup replacing the original error.** `with db:` could replace a hook
   exception with an error raised by rollback or connection closure. Cleanup
   still runs, but the original exception is raised with the cleanup error as
   its cause and an explanatory note. Cleanup errors on otherwise successful
   scope exit continue to propagate normally.

Five new unit cases failed before these fixes. They are separate from the
question of adopting legacy retry semantics: they enforce the native policy
already documented for failed operations and original-error propagation.

## Verification and reproduction

- Targeted session/table/configuration suite: 89 passed.
- PostgreSQL acceptance includes the 16-case native matrix plus before/after
  hook failures crossing named connections, observed from an independent connection.
- Complete source suite on isolated PostgreSQL 17: **562 passed**, no skipped or
  xfail cases; coverage **95%**. This includes nine new test cases over the
  previous 553-test baseline, with the 16-scenario matrix exercised inside one
  of those acceptance tests.
  The subsequent [caller review](21-recovery-callers.md) adds five recovery
  cases and records the updated full-suite result: **567 passed**, coverage 95%.
- Ruff passed for source, tests and the new oracle; mypy passed on 32 source files.
- Sphinx HTML build passed with warnings treated as errors; `git diff --check`
  passed. These are local results; no release or CI result is implied.

Run the oracle separately in an environment with psycopg and the selected
implementation's dependencies; use an isolated PostgreSQL service:

```sh
python docs/design/evidence/python_error_oracle.py \
  --legacy-root /path/to/genropy --dsn "$TEST_DSN" --output /tmp/legacy-errors.json
PYTHONPATH=src python docs/design/evidence/python_error_oracle.py \
  --dsn "$TEST_DSN" --output /tmp/native-errors.json
```

The script creates and drops only uniquely named `python_error_*` schemas.
Recorded results describe the baseline, not automatic approval of its differences.
