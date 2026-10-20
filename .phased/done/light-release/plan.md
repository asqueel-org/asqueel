# Context: plan/write-cycle
Parent: codex/core-release-0.6 | Issue: #27
Mode: manual
Theme: light release
Must not break: read/write contracts of docs/design/97, 99, 111 (single hierarchical model, separate SELECT and DML compilers, common execution, record and lock on the caller's connection, NamedList rows)
Must not break: the full suite result of merge-read-write (4739 passed, 42 skipped, 32 strict xfail citing asqueel-org/asqueel#15, #17-#32)

## Objective
Declare a light first version of asqueel for a new project: read, insert, update, delete, formulas and aggregations on PostgreSQL and SQLite, proven by one end-to-end example, with documentation that matches the code and states the limits. No new feature: issues #15 and #17-#32 stay open, except #27 (documentation), which this workflow resolves.

## Work Plan
- [x] **Phase 1**: the tutorial becomes the end-to-end example on PostgreSQL and SQLite
  - Run: opus / medium
  - Pattern: `docs/guide/_examples/shop_tutorial.py` (model, deployment, seed, reads, changes, run sections); `tests/sqlite/test_migration_api.py` (migrate on SQLite); `tests/many_aggregations/` (`.aggr()` usage); `examples/sqlite/configure.py` (SQLite deployment)
  - Files: `docs/guide/_examples/shop_tutorial.py`, `tests/documentation/test_examples.py`, `src/asqueel/compiler.py` (exists= double parenthesis, notes.md § Phase 1) and its SQLite regression test
  - Decisions: tables are created by `db.migrate()` (src/asqueel/application.py:123), not by hand-written DDL. The flow is insert → read (relation path `@customer_id.name`, one formula, one `.aggr()` aggregation) → update → read → delete → read, with one rollback check. Only tables the light version can write: no options, no `default=`/`default_from`, single-column pkey. The tutorial's section markers (`# model-start` ... `# run-end`) stay, because docs/guide/tutorial.md includes them. No new API.
  - Details: rewrite `create_tables` as the migration step, add the aggregation to the reads and a delete step to the changes, and make `run()` work for a PostgreSQL DSN and a SQLite file. Parametrize `test_downloadable_tutorial` over both dialects (PostgreSQL marked as today). Keep `test_application_query_guide_against_tutorial_data` and `test_application_environment_examples` working on the new tutorial.
  - Done: `venv/bin/python -m pytest tests/documentation --no-cov -q` passes, with `test_downloadable_tutorial` run on PostgreSQL and SQLite; `venv/bin/ruff check src tests scripts docs/guide/_examples` passes; full suite unchanged from Must not break.
  > Done: the tutorial creates its tables with db.migrate() and runs insert, reads (@customer_id.name, formulas, @invoices.aggr), update, rollback check and delete on PostgreSQL and SQLite; run(dsn=None) picks SQLite in a temporary directory. exists= formulas fixed on SQLite (EXISTS ( SELECT ... )), reopening the recorded legacy limit by user decision. tests/documentation 11 passed (tutorial on both dialects); ruff clean; full suite 4741 passed, 42 skipped, 32 xfailed (baseline + 2 new tests).
  > Files: docs/guide/_examples/shop_tutorial.py, tests/documentation/test_examples.py, src/asqueel/compiler.py, tests/sqlite/test_sqlite_exists_formula.py, tests/native_formulas/test_subquery_results.py, tests/native_formulas/test_subquery_method_results.py, docs/design/58-compiler-checklist.md, docs/design/98-single-read-path.md, .phased/active/light-release/notes.md
  > Review: 5 skips "EXISTS formula not supported on SQLite" remain in the unchanged legacy corpus (tests/native_formulas/legacy_subqueries.py:86,183,266,307; test_tree_legacy_formulas.py:86); after the fix they could run on SQLite.

- [x] **Phase 2**: documentation matches the code, and the wheel installs clean
  - Run: opus / medium
  > Batches: 1 limitations.md as the light-version perimeter | 2 models.md (#27), queries.md `.aggr()`, tutorial.md, quickstart.md, writes.md | 3 wheel build and clean install
  - Pattern: `docs/guide/limitations.md` (existing status table shape); `tests/many_aggregations/` for the `.aggr()` behaviour the guide states
  - Files: `docs/guide/limitations.md`, `docs/guide/models.md`, `docs/guide/queries.md`, `docs/guide/tutorial.md`, `docs/guide/quickstart.md`, `docs/guide/writes.md`
  - Decisions: `limitations.md` stays the single status page; it states what the light version does and what it refuses, each refusal linked to its issue: `sys_fields` #29, `default`/`default_from`/newrecord #28, `hierarchical` #30, `auto_counter` #31, composite-pkey reads #26, recordToUpdate #17, batchUpdate #32, partitions on write #15. Claims are checked against the code and the tests, never copied from design docs. Commit messages reference #27 with `Refs #27`, never `Closes`. No version change, no release notes, no push.
  - Details: rewrite limitations.md (remove stale claims: soft-delete/restore, RETURNING results, "record reads and model writes remain disconnected"); fix models.md:160-162 and 188-189 (#27); add the `.aggr()` section to queries.md and remove the statement that aggregates need explicit SQL; align tutorial.md, quickstart.md and writes.md with the Phase 1 tutorial and the write cycle. Build the wheel, install it in a fresh venv outside the repo with its published dependencies, and run the tutorial from that install on PostgreSQL and SQLite.
  - Done: `venv/bin/python -m sphinx -W -b html docs docs/_build/html` passes; `venv/bin/python -m pytest tests/documentation --no-cov -q` passes; `grep -n "model.ui" docs/guide/models.md` is empty; the wheel from `venv/bin/python -m build --wheel` installs in a fresh venv and `run()` of the installed tutorial completes on PostgreSQL and SQLite (commands and output recorded in notes.md § Phase 2).
  - Verify: now — read limitations.md: it says what a new project can and cannot do today, with the right issue for each limit.
  > Done: limitations.md is the light-version perimeter (what works; every refusal of require_write_capabilities with its issue or "no issue yet"; #15 #17 #26 #28 #32 and open defects #16 #18-#25); writes.md rewritten on insert/update/delete with the legacy cycle and the sql_* variants; models.md fixed for #27 (model.ui removed, alias keys skipped in writes, RETURNING of database-decided columns); queries.md gains the aggr() section; tutorial.md covers SQLite, db.migrate(), aggr() and delete; quickstart.md unchanged. sphinx -W clean; tests/documentation 11 passed; wheel (uv build) installed in clean venvs: tutorial run() completes on SQLite and PostgreSQL with [postgresql,migration], quickstart with [postgresql] only; full suite 4741 passed, 42 skipped, 32 xfailed. Comment posted on #27 correcting the originalColumn claim.
  > Files: docs/guide/limitations.md, docs/guide/models.md, docs/guide/queries.md, docs/guide/tutorial.md, docs/guide/writes.md, .phased/active/light-release/notes.md, .phased/active/light-release/plan.md
  > Review: docs/guide/hooks.md, row-policies.md, cheatsheet.md and release-notes.md, outside Files, still name raw_insert/raw_update/raw_delete, soft_delete or returning=, which the code no longer has; transactions.md and troubleshooting.md were not checked against the write cycle.
  > Verify: now — read limitations.md: done, user ok 2026-10-16.

## Notes
- Adopted branch plan/write-cycle, worktree worktrees/write-cycle; the merge-read-write plan is archived in .phased/done/.
- Test environment: memory note asqueel-test-environment (venv/ with -e .[dev,docs]; call tools as `venv/bin/python -m <tool>`).
- Commits carry no AI attribution and no Co-Authored-By line.

## Quality check
> Quality check: 2026-10-17T05:29:27Z — commit 80dc2a1 — review extended, QA done, findings 6 confirmed, 0 dismissed, final touch 5 corrections
