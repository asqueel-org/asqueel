# Context: wf/merge-read-write
Parent: plan/write-cycle
Mode: manual
Theme: read-write merge
Must not break: read/write contracts of docs/design/97, 99, 111 (single hierarchical model, separate SELECT and DML compilers, common execution via prepare_sql/CompiledQuery/db.execute, record and lock on the caller's connection and transaction, NamedList rows)
Must not break: the open merge in worktrees/write-cycle stays untouched (no reset, abort or commit there)

## Objective
Merge the read path (`codex/core-single-read-path`, commit `7cee8e8`, which contains `d1c6149` and `531d87b`) into the write cycle, integrate everything that works together, and turn every remaining problem into a drafted GitHub issue. No new features in this workflow: deferred items (newrecord, sys_fields, default/default_from, hierarchical, auto_counter, recordToUpdate, batchUpdate) become issues, not code. The issues are analysed afterwards, outside this plan.

## Work Plan
- [x] **Phase 1**: merge the read path and attribute every failure of the full suite
  > Done: merge 8e6222f without conflict; attribution.md lists the 134 failures (98 failed + 36 errors), all R in 10 root causes, none new versus the pre-merge tip 1995fe4; no deletion; ruff and mypy pass
  > Files: .phased/active/merge-read-write/attribution.md, .phased/active/merge-read-write/notes.md, .phased/active/merge-read-write/plan.md (merge commit 8e6222f brings in the read path)
  > Verify: now — done by the user: classes stand on the contracts and the legacy; no test deleted, every proposed deletion became a realign row
  - Run: opus / medium
  - Pattern: `library-standard` (git merge, pytest)
  - Files: no source or test edit; output in `.phased/active/merge-read-write/notes.md` (## Phase 1) and `.phased/active/merge-read-write/attribution.md`
  - Decisions: verified at planning (2026-10-16): `git merge-tree --write-tree 1995fe4 7cee8e8` reports no conflict; the index staged in worktrees/write-cycle equals the automatic merge of 1995fe4 + 531d87b (tree 1f605ef), so no manual resolution needs preserving. camelCase query options (`excludeDraft`, `excludeLogicalDeleted`, `ignorePartition`) are mapped to snake names by `_ALIASES` in `src/asqueel/application_table.py` on both branches: no rename. Classes: R = old test to realign to the merged API, B = integration bug in code, O = out of scope (deferred feature or legacy gap) to become an issue.
  - Details: `git merge --no-ff 7cee8e8` (message `merge: read path 7cee8e8 into write cycle`). Check that the 16 files of the open merge (`git -C ../write-cycle diff --cached --name-only`) have, in the merged tree, content compatible with `git -C ../write-cycle show :<path>`; record any difference. Create `venv/` (`uv venv venv --python 3.12 && uv pip install --python venv/bin/python -e ".[dev,docs]"`). Run the whole suite without `tests/read_path/pytest.args`, PostgreSQL on 127.0.0.1:5432 and SQLite: `venv/bin/python -m pytest tests --no-cov -q -rfE -p no:cacheprovider`. For every failed or errored nodeid write one row in `attribution.md`: nodeid | class R/B/O | cause in one line | evidence (error line, file:line). Group rows by root cause. Run `venv/bin/ruff check src tests scripts` and `venv/bin/python -m mypy src/asqueel` and attribute their errors the same way.
  - Done: merge commit exists; `attribution.md` lists every nodeid from the `-rfE` summary (count of rows == count of failures + errors), each with exactly one class; no file outside `.phased/` changed after the merge commit (`git diff --stat <merge commit> HEAD -- . ':!.phased'` empty).
  - Verify: now — read attribution.md: each class is right; every test proposed for deletion is approved or refused by you, one by one.

- [>] **Phase 2**: integrate — fix the approved R and B rows  `vast`
  > In execution since 2026-10-16T16:56:52Z
  - Run: opus / high
  > Batches: 1 B rows (code) | 2 R rows per test area, one batch per area in attribution.md | 3 O rows marked xfail
  - Pattern: contracts in `../../asqueel-read-path/docs/design/97-read-write-contracts.md`, `99-writer-handoff-single-read-path.md`, `111-read-write-integration-handoff.md` (merged into `docs/design/` by Phase 1); write tests `tests/write_compiler/test_write_cycle.py` as the model for realigned DML tests
  - Files: the files named by the approved rows of attribution.md
  - Decisions: no shim, no restored API (QueryPlan, Fragment, SqlStatement, driver.prepare, writes.py), no new syntax, no recovered deferral, no rename. A test is deleted only if Phase 1's Verify approved it. O rows are marked `pytest.mark.xfail(strict=True, reason="issue draft <n>: <one line>")`; rows already covered by an open issue use `reason="asqueel#<number>: <one line>"`, where <n> is the draft number Phase 3 will use (assign it here, in attribution.md).
  - Details: fix B rows in code following the contracts; realign R rows to the merged API. Re-run the lock, record and named-connection tests on both dialects (contention with a second connection, release on rollback, no implicit commit). Record every non-obvious choice in notes.md under ## Phase 2.
  - Done: `venv/bin/python -m pytest tests --no-cov -q` green on PostgreSQL and SQLite with only the O xfails; `venv/bin/ruff check src tests scripts`, `venv/bin/python -m mypy src/asqueel`, `venv/bin/python -m sphinx -W -b html docs docs/_build/html` pass; every xfail reason names a draft number present in attribution.md.

- [ ] **Phase 3**: draft one issue per remaining problem
  - Run: opus / low
  - Pattern: `new-pattern`
  - Files: `.phased/active/merge-read-write/issues/<n>-<slug>.md`
  - Decisions: target repository `asqueel-org/asqueel`. Issues are written in English. Opening them on GitHub needs the user's explicit ok at this phase; nothing is opened before.
  - Details: one draft per O root cause from attribution.md, plus one per deferral not already covered: newrecord (with default/default_from, which `require_write_capabilities` in `src/asqueel/model_source.py` refuses), sys_fields, hierarchical, auto_counter, recordToUpdate, batchUpdate. Each draft: title, what fails or is missing (consequence for a project using asqueel), evidence (tests, file:line), references to the write-cycle plan or the design docs, no proposed solution beyond what is already decided. After the user's ok, open them with `gh issue create`, then replace each `issue draft <n>` in xfail reasons with `#<number>`.
  - Done: every O row and every listed deferral maps to exactly one draft; after opening, `grep -rn "issue draft" tests` is empty and the suite result equals Phase 2's.
  - Verify: now — read the drafts and give the ok to open them.

## Notes
- Worktree at `worktrees/merge-read-write` (user convention), not `.claude/worktrees/`.
- No push, no publication, no version change.
- Commits carry no AI attribution and no Co-Authored-By line.
- Test environment: memory note asqueel-test-environment (call tools as `venv/bin/python -m <tool>`).
