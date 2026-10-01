# 25 — Deferred callback recovery: verified behavior and accepted decision

Historical comparison. Superseded on 1 October by [F1 closure 27](27-f1-request-lifecycle-closure.md),
which removes forced queue disposal after Python postcommit exceptions.

Status at the time of this comparison: verified after `022132b`; no runtime callback policy
was changed. The normal-save protection remains in place. This report does not
close F1 or silently accept every legacy difference.

## Reproduced comparison

The existing `evidence/python_error_oracle.py` was rerun for both implementations
against isolated PostgreSQL: 16 scenarios each. Original legacy AST methods and
the real Bag execute at revision `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
The retained callback results and source hashes are in
[evidence/callback_recovery_oracle.json](evidence/callback_recovery_oracle.json).
The fixture boundaries from review 20 still apply; this is not a full web request.

Each callback raises the same Python exception, optionally after writing another
row. Another callback is queued behind it. The caller tries commit again, then
rolls back and starts a fresh transaction.

| Case | Legacy | Current native behavior |
|---|---|---|
| PY02: before commit fails | A second commit runs the remaining callbacks and can persist partial callback work. | A second commit is blocked until rollback; rollback clears both queues. |
| PY03: after commit fails after new SQL | The original commit is durable; retry commits the new work and drains remaining callbacks. | Original commit remains durable; new work is rollback-only; remaining callbacks are discarded. |
| PY04: after commit fails without new SQL | Retry does nothing immediately; remaining callbacks run on a future transaction's commit. | Retry does nothing; remaining callbacks are discarded and never attach to later work. |

Neither implementation reruns the failing callback automatically: it was removed
before invocation. Thus legacy queue continuation is not retry of the failed
operation. External effects already performed by a callback cannot be undone
by SQL rollback in either implementation.

## Clarified decision — 1 October 2026

Callback errors follow ordinary Python propagation. If the callback implementer
catches an expected failure and returns normally, dispatch continues. If the
exception escapes, dispatch stops and the caller sees it. The earlier SQL commit
is already durable. Asqueel must not catch failures merely to continue with the
next callback or aggregate errors after completing the queue.

This decides propagation, not retention of callbacks that were never reached.
The current runtime clears residual postcommit callbacks; legacy can retain them.
That separate cleanup difference is still recorded, not implicitly approved by
this clarification. The attempted continue-on-error change was withdrawn before
verification; the runtime remains unchanged.

Catching a SQL/table-write error does not repair transaction state or bypass
existing rollback protections. F1 remains open for residual-queue disposition
and the separate caller-specific error paths from review 21.

## Verification

`tests/application_connections/test_callback_recovery.py` adds eight real-database
cases: before/after commit × callback with/without new SQL × PostgreSQL/SQLite.
They verify original exception identity, restored committing context, retry
barriers, committed data from an independent connection after recovery, clean
queues and a successful new unit of work with new callbacks.

Complete suite: **637 passed**, **95% coverage**. Ruff passes for the new tests.
After the decision, two additional before/after cases verify that a callback
which catches an external-service error lets the queue continue without replay.
The targeted deferred suite passes all **20 tests**; documentation builds without
warnings. The 637-test result above predates these two additional cases.
The independent caller-error review from report 21 remains open after this slice.
