# 29 — Review corrections before publishing 0.4.0

Review input: `temp/review_2026-10-01.md`, against `960b638`.
This report closes the two reproduced defects and the runtime documentation/demo
corrections. It does not mark every observation in the review as resolved.

## Composite foreign keys

Resolved relation declarations now carry the effective relation name, including
the owning composite name when no x_name is supplied. Physical projection no
longer loses that declaration by guessing its name from the first member column.
Regression tests cover named/unnamed composites, optional physical constraints,
and remapped physical schemas/tables/columns. The unnamed physical case failed
before the change. A real PostgreSQL migration applies the composite FK, rejects
an invalid child row and enforces ON DELETE CASCADE.

SQLite's migration adapter does not support FK DDL; this existing documented
backend limitation is not fixed by preserving migration metadata.

## Connection configuration

An omitted connection implementation inherits the DB implementation (PostgreSQL
by default); an explicitly supplied connection implementation takes precedence.
A connection node with an unresolved name is still rejected, not mistaken for
legacy conninfo configuration. Tests cover both backends and both explicit
override directions. SQLite inheritance failed before the change.

## Documentation and executable example

Removed stale application-session terminology in current guides, corrected
execute/commit and SQL rollback descriptions, documented connection inheritance,
and clarified that the application compatibility adapter is future work.
The native demo now uses explicit completion and cleanup, verified in both
facade and injected-adapter modes against isolated PostgreSQL. Release guidance,
the site introduction and the design index reflect the current implementation.
The importer minimum is now explicitly PostgreSQL 15 because of catalog columns.

## Multi-row write contract: review evidence and subsequent decision

At legacy revision `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`:

- `gnrpy/gnr/sql/gnrsql/write.py`, update/delete: operate on a record and fire hooks.
- `gnrpy/gnr/sql/gnrsqltable/crud.py`, deleteSelection: selects locked rows and
  calls delete for each record.
- The same module's batchUpdate/_batchUpdate_rows selects rows and calls update
  (or raw_update) per record, with separately configurable completion.

At the time of this review, Asqueel permitted set-based predicates without hooks
and required one record when hooks were present. The subsequent user decision
in [decisions 05](05-decisions.md) resolves this: ordinary update/delete always
require one record; raw predicates may affect many rows; raw_insert accepts one
mapping or a list. No separate Many API. Shared raw hooks receive operation data,
not implicit full-row snapshots. Broader F4 acceptance remains open.

## Validation and remaining scope

659 tests pass on PostgreSQL/SQLite, 95% coverage; the demo passes in both modes.
Ruff and mypy pass. Sphinx is validated with warnings as errors.

Other review items remain separate: environment API uniformity, concurrent recipe
imports, dependency compatibility policy, public API cleanup, documentation
language and archive/asset housekeeping. Automatic SQL rollback and per-thread
cleanup are intentional contracts. The connection ownership guard is exercised
by cross-thread private-state misuse tests, so calling it unreachable overlooks
that protection. No dependency bounds, archived files or release tags are changed.
