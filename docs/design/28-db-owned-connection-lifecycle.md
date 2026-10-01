# 28 — F1 structural closure: DB-owned connection lifecycle

1 October 2026. Correction to the premature F1 closure in commit `13d48b2`.
That commit verified behavior but left the internal Session entity in place.
This delivery removes it and closes the synchronous F1 profile, including the
agreed architecture. F0 inventory and F2–F10 remain open.

## Implemented structure

- Deleted `src/asqueel/session.py`; no replacement lifecycle object or facade.
- Database directly owns execution, commit, rollback, deferred callbacks,
  failure state and connection cleanup. Public DB calls remain unchanged.
- Its thread-local named-connection dictionary contains plain dictionaries.
  `_ConnectionState` is a TypedDict annotation, not an independent runtime API.
  Records hold the physical connection, ownership, flags, queues and outcomes.
- `DeferredCommitError` lives in `errors.py`; its root package export remains.
- Tests formerly under `tests/application_session` now live under
  `tests/application_connections` and exercise Database. Legacy oracle adapters
  use the same DB implementation.

The data remains necessary to preserve independent named transactions, callback
queues, failure barriers and ownership checks. There is no separate session to
construct, acquire, complete or close. Connection acquisition remains lazy.

## Acceptance

- Full PostgreSQL/SQLite suite: **650 passed**, **95% coverage** after removal.
- Ruff passes; mypy passes for **39 source files** (one module deleted).
- Strict Sphinx build with warnings as errors passes.
- Source, tests and executable evidence contain no Session imports, `_session`
  or `_sessions` access. Historical reports and SQLAlchemy comparisons can name
  sessions; they do not introduce a runtime entity.

Existing acceptance covers two requests on one shared DB/thread, independent
named connections, cross-thread misuse, callback ordering and failure, SQL and
Python recovery, uncertain completion and cleanup failures. Report 27 retains
the original legacy caller evidence and application adaptation boundaries.

## Async consequence

The ownership check is isolated on Database. A future async runtime must replace
thread-local access with task-owned context and await driver operations. Plain
mutable records still require fresh allocation and exclusive connection
ownership; ContextVar alone does not provide isolation. No async support or
unchanged synchronous I/O signatures are promised. See report 26.

This is a source correction, not a new package version or PyPI publication.
