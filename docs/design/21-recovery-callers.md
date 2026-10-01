# 21 — Recovery in real legacy callers

Historical review, 30 September 2026. The remaining caller boundaries below
were subsequently executed and assigned in [closure report 27](27-f1-request-lifecycle-closure.md).
Its results supersede this report’s open F1 status; the earlier evidence remains historical.

**Keep the existing native rollback policy for now.** The
verified recovery paths work with it: discard failed work before continuing,
write an independent failure log, or catch an external service error and save
its status. These results do not approve every difference in deferred retry
semantics, close F1, or certify the whole legacy application.

## Sources and review coverage

The [catalog generator](evidence/catalog_recovery_callers.py) reads the Git
archive at legacy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`: **1,648 Python
files parsed, 517 exception handlers, 61 candidate try blocks**, no parse errors.
Three modified invoice example files in the working tree were excluded. The
[catalog](evidence/recovery_callers_catalog.json) records paths, source hashes,
scopes and calls; the [review index](evidence/recovery_callers_review.md)
classifies all 61 candidates, including try/finally blocks without handlers.

Selection is lexical: writes in try/except, transaction calls in the enclosing
scope, or trigger/onCommitting methods. It is not alias analysis or an exhaustive
dynamic call graph. A later syntactic commit is not necessarily reachable from
an exception handler. External consumers remain outside this inventory.

## Executed caller contracts

The [caller oracle](evidence/recovery_caller_oracle.py) executes unchanged AST
method bodies from five original callers against both the legacy core and native
Asqueel on isolated PostgreSQL. Its [results](evidence/recovery_caller_oracle.json)
cover **nine scenarios per implementation**. Independent observer connections
check persisted rows before and after cleanup.

| Caller | Injected failure | Observed recovery |
|---|---|---|
| Active `email/lib/imap.py::receive` | After-insert Python error, SQL error, deferred error | Roll back failed message, advance checkpoint, commit subsequent message. Failed message and hook writes disappear on both backends. |
| `sys/upgrade.py::runUpgrade` | Python hook error, deferred error | Roll back failed upgrade before saving error log in a new transaction, on both backends. |
| `BaseResourceBatch.__call__` | Python hook error | Report failure; commit log through independent `system` connection. Failed main write disappears on cleanup. |
| `email/message.py::sendMessage` | SMTP service error | Catch external error and persist failure status. No database write has failed in this scenario. |
| `GnrAppLoggingHandler._process_record` | Python hook error, SQL error; then another log | SQL errors recover on both. Python errors expose missing caller rollback, detailed below. |

The fixture supplies service, mail, scheduler, lookup and record-context stubs;
it uses the original core lifecycle and real legacy Bag, with the bounds from
[report 20](20-python-error-lifecycle.md). Native `rollbackAll` in this harness
maps to rollback of the selected single-store session. This is not an added
native API or a certification of multiple stores, HTTP, actual SMTP/IMAP,
attachment processing or the entire record-cluster implementation.

Five portable native PostgreSQL regression cases cover rollback/log/next-item
recovery for Python, SQL and deferred failures, independent system logging,
and storing a handled external failure as status. They also assert that failed
work's after-commit callbacks do not leak into the next successful transaction.

## Concrete porting risk: logger catches without rollback

The logging worker continues after `_process_record` catches an exception.
If an ordinary Python after-insert hook fails, the first log and its hook writes
remain pending in legacy. In the experiment, the next log's commit persists
**both logs and the failed hook's audit row**. Native Asqueel blocks the next
write until rollback, so neither log persists before final cleanup.

This is evidence of a real caller that needs recovery review, not evidence that
retaining a failed log's partial effects is intended behavior. A port should
roll back the logging transaction after failure before processing the next
message. The external Genropy source was not changed. Normal web saves still
skip commit on failure, as demonstrated by the save-handler oracle in report 20.

## Remaining boundaries and next work

- The older `email/lib/utils.py` helper can catch a parsing failure after
  attachment inserts without rollback. The inspected active importer selects
  `imap.py`; external use of the older helper is unknown.
- Mail batch logging and SMTP queue removal have broad catch scopes including
  database writes. Only the external-service failure path above was executed;
  database failure in those branches needs separate porting tests.
- Extension DDL and directory visitor callbacks need caller-specific review;
  multi-store bulk/raw fallback belongs to its own contract.
- Pre/post-commit residual callback retry differences PY02–PY04 remain open.
  None of these caller experiments establishes a requirement to retain partial
  failed hook writes or residual callback queues.

F1 therefore remains open for those precise error boundaries and locale/workdate
completion. The next independent implementation slice is the locale/workdate
contract, starting from legacy evidence. No rollback policy change, release or
push is part of this review.

## Verification

- Original-caller oracle: nine scenarios per backend passed; the sole recorded
  difference is the logger's Python-error path.
- Full native suite on isolated PostgreSQL 17: **567 passed**, no skips or
  xfails, coverage **95%**; five recovery cases added to the prior 562-test run.
- Ruff passed for source, tests and all four new evidence scripts; Sphinx HTML
  passed with warnings as errors; `git diff --check` passed.
- A broader Ruff scan also found 11 pre-existing formatting violations in
  `evidence/takeover_deferred_probes.py`, which this work did not modify.

The initial deferred regression test expected the queued exception type itself;
it was corrected to expect the public `DeferredCommitError` raised at commit.
No runtime change was needed for any of these new recovery tests.
