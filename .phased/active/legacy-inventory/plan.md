# Context: plan/write-cycle
Parent: codex/core-release-0.6
Mode: autonomous
Theme: legacy inventory
Must not break: source code and tests unchanged — this workflow writes documentation only (docs/design/112-legacy-inventory.md, docs/guide/legacy-features.md, docs/guide/legacy.md link, docs/index.rst toctree, docs/review/asqueel-vs-genropy-0.6-it.html)
Must not break: docs/review/asqueel-vs-genropy-it.html stays byte-identical (user decision 2026-10-17: new version, never edit the old one)
Must not break: `venv/bin/python -m sphinx -W -b html docs docs/_build/html` passes after every phase

## Objective
Describe asqueel 0.6 against GenroPy legacy for the release: one verified inventory of every legacy SQL-layer feature (present, different, missing) and every new asqueel feature, with the motivation of each difference and alternative proposals for each missing item. From it, an English Sphinx chapter for external users and a new Italian review page for the team.

## Work Plan
- [x] **Phase 1**: inventory, areas 1-4 (model, query, formulas, relations)
  > Done: docs/design/112-legacy-inventory.md with `## Fonti` and areas 1-4: 94 rows (27 model, 26 query, 20 formulas, 21 relations); check_inventory.py --areas 1-4 exits 0, sphinx -W passes, no diff under src/tests.
  > Files: docs/design/112-legacy-inventory.md, .phased/active/legacy-inventory/plan.md, .phased/active/legacy-inventory/notes.md
  - Pattern reference: `docs/design/95-develop-reference-audit.md` (legacy reference and file:line citation style); `docs/adattamenti-legacy.md` (existing present/missing classification to re-verify, not to copy)
  - Files: `docs/design/112-legacy-inventory.md` (new)
  - Decisions: Legacy reference = GenroPy commit `95da66ee64b0c789dbb6b35254011d83ce1911c5` (doc 95), read with `git -C ~/Sviluppo/Genropy/genropy show 95da66ee:<path>`, scope `gnrpy/gnr/sql/`; asqueel = this branch. Document in Italian (docs/design convention). Exact format, enforced by `.phased/active/legacy-inventory/check_inventory.py`: one `## <n> <Area>` heading per area (`## 1 Modello`, `## 2 Query`, `## 3 Formule`, `## 4 Relazioni`, `## 5 Scritture`, `## 6 Transazioni`, `## 7 Migrazione`, `## 8 Dialetti`), each followed by one table `| ID | Funzione | Legacy | Asqueel | Stato | Motivazione | Alternative |`; ID `A<area>.<n>`; Stato one of `presente`, `diverso`, `mancante`, `nuovo`; references as `gnrpy/<path>.py:<line>` and `src|tests|docs/<path>:<line>`. A `diverso` or `nuovo` row cites its source in Motivazione: a public doc path, an issue `#n`, or `decisione utente YYYY-MM-DD` for decisions recorded only outside the repo. A `mancante` row names its issue (`#15`, `#17`-`#32`) or `nessuna issue`, and gives at least two alternatives `(a) ... (b) ...` (implement as legacy, implement differently, leave out with the workaround) without choosing. Never name or link files under `temp/` (private). A `## Fonti` section before the areas states both revisions. Claims come from reading the code, never from design docs alone; when a design doc and the code disagree, the code wins and the row says so.
  - Details: for each area list the legacy features of `gnrpy/gnr/sql` (gnrsqlmodel, gnrsqldata, gnrsqltable, adapters as relevant) a project uses, find the asqueel counterpart, classify, cite. Add the asqueel features with no legacy counterpart as `nuovo` (e.g. `.aggr()` aggregations, virtualRelation `table=`, SQLite support). Granularity: one row per feature a project calls or declares (a method, an attribute, a macro), not per internal helper.
  - Done: `venv/bin/python .phased/active/legacy-inventory/check_inventory.py --areas 1-4` exits 0; `venv/bin/python -m sphinx -W -b html docs docs/_build/html` passes; `git diff --stat "$(git log -1 --diff-filter=A --format=%H -- .phased/active/legacy-inventory/plan.md)" -- src tests` is empty.

- [x] **Phase 2**: inventory, areas 5-8 (writes, transactions, migration, dialects)
  > Done: docs/design/112-legacy-inventory.md gains areas 5-8 (30 writes, 29 transactions, 29 migration, 23 dialects) and `## Riepilogo` (205 rows: 45 presente, 76 diverso, 68 mancante, 16 nuovo); check_inventory.py --areas 1-8 exits 0, sphinx -W passes, no diff under src/tests.
  > Files: docs/design/112-legacy-inventory.md, .phased/active/legacy-inventory/plan.md, .phased/active/legacy-inventory/notes.md
  - Pattern reference: Phase 1 rows of `docs/design/112-legacy-inventory.md`; `docs/guide/limitations.md` (write refusals and their issues); `docs/design/97-read-write-contracts.md`
  - Files: `docs/design/112-legacy-inventory.md`
  - Decisions: same as Phase 1. Writes cover the legacy write cycle (insert/update/delete, triggers, protect_*, deleteRelated/updateRelated, raw commands, newrecord, recordToUpdate, batchUpdate, sys_fields, counters, hierarchical); transactions cover connections, commit/rollback, locks, deferred blocks; migration covers gnrsqlmigration against asqueel-migration; dialects cover PostgreSQL and SQLite adapters. Write decisions recorded only in the private write-cycle plan are cited as `decisione utente 2026-10-16` with the reason in one sentence.
  - Details: as Phase 1, areas 5-8. Close the document with `## Riepilogo`: per area the count of each Stato.
  - Done: `venv/bin/python .phased/active/legacy-inventory/check_inventory.py --areas 1-8` exits 0; `venv/bin/python -m sphinx -W -b html docs docs/_build/html` passes; `git diff --stat "$(git log -1 --diff-filter=A --format=%H -- .phased/active/legacy-inventory/plan.md)" -- src tests` is empty.

- [x] **Phase 3**: English Sphinx chapter for external users
  > Done: docs/guide/legacy-features.md with the 8 areas (works as in GenroPy / differently / not available yet) and a new-features section; all 205 inventory IDs appear exactly once as `(A<n>.<m>)`; linked from docs/guide/legacy.md and the docs/index.rst toctree. sphinx -W passes; 20 `issues/` lines vs 8 distinct issues in mancante rows (#17, #18, #26, #28-#32); no diff under src, tests, docs/review.
  > Files: docs/guide/legacy-features.md, docs/guide/legacy.md, docs/index.rst, .phased/active/legacy-inventory/plan.md, .phased/active/legacy-inventory/notes.md
  - Pattern reference: `docs/guide/limitations.md` (tone and table shape of the status page); `docs/guide/legacy.md` (existing chapter for GenroPy users)
  - Files: `docs/guide/legacy-features.md` (new), `docs/guide/legacy.md` (one link to the new page), `docs/index.rst` (toctree entry after guide/legacy)
  - Decisions: English; derived only from the inventory, no new claim. Organised by the same 8 areas; per area three lists: works as in GenroPy, works differently (with the reason in one sentence), not available yet (with issue link `https://github.com/asqueel-org/asqueel/issues/<n>` and the workaround); then a section of new features. Alternatives under discussion are NOT in this page (they are team material). `legacy.md` keeps its text; it only gains the link.
  - Details: write the page; every `diverso`/`mancante`/`nuovo` row of the inventory appears exactly once.
  - Done: `venv/bin/python -m sphinx -W -b html docs docs/_build/html` passes; `grep -c "issues/" docs/guide/legacy-features.md` is at least the number of distinct issues cited by `mancante` rows of the inventory; `git diff --stat "$(git log -1 --diff-filter=A --format=%H -- .phased/active/legacy-inventory/plan.md)" -- src tests docs/review` is empty.

- [x] **Phase 4**: new Italian review page for the team
  > Done: docs/review/asqueel-vs-genropy-0.6-it.html, self-contained (inline CSS from the old page, no script, no external link): header with both revisions and date, summary table of counts, 8 area sections (presente collapsed, diverso with motivation, 68 mancante as open points with alternatives side by side, nuovo). HTMLParser exits 0; all 205 inventory IDs found; sphinx -W passes; no diff under src, tests, docs/review/asqueel-vs-genropy-it.html.
  > Files: docs/review/asqueel-vs-genropy-0.6-it.html, .phased/active/legacy-inventory/plan.md, .phased/active/legacy-inventory/notes.md
  > Verify: now — open docs/review/asqueel-vs-genropy-0.6-it.html in a browser, light and dark theme, and check the layout at phone width.
  - Pattern reference: `docs/review/asqueel-vs-genropy-it.html` (CSS variables, status colours legacy/decided/open/proposed, light/dark theme, section layout) — copy the style, not the content
  - Files: `docs/review/asqueel-vs-genropy-0.6-it.html` (new)
  - Decisions: Italian; self-contained HTML (inline CSS, no external script); derived only from the inventory. Per area: rows present (collapsed), differences with motivation, missing items with issue and the alternatives (a)/(b)/… shown side by side as open points for discussion, new features. A header states both revisions and the date, and says it supersedes, without changing, the page of 5 October. The old page is not modified.
  - Details: one section per area plus a summary table of counts; every inventory row appears once.
  - Done: the file exists and `python3 -c "import html.parser,sys; html.parser.HTMLParser().feed(open('docs/review/asqueel-vs-genropy-0.6-it.html').read())"` exits 0; for each inventory ID, `grep -c "A<area>.<n>" docs/review/asqueel-vs-genropy-0.6-it.html` ≥ 1 (scripted over all IDs of docs/design/112-legacy-inventory.md); `git diff --stat "$(git log -1 --diff-filter=A --format=%H -- .phased/active/legacy-inventory/plan.md)" -- src tests docs/review/asqueel-vs-genropy-it.html` is empty.

## Notes
- Adopted branch plan/write-cycle, worktree worktrees/write-cycle. Commits carry no AI attribution.
- The checker is the executable contract of Phases 1-2: read-only for the phases; a false premise in it is a plan-defect claim.
- Reading the legacy outside the repo uses only `git -C ~/Sviluppo/Genropy/genropy show|ls-tree|grep` at the fixed commit; no checkout or fetch there.
- Test environment: venv/ in the worktree (memory note asqueel-test-environment).

## Suggested execution config
| Phase | Effort | Model |
|-------|--------|-------|
| Phase 1 | high | opus |
| Phase 2 | high | opus |
| Phase 3 | medium | opus |
| Phase 4 | medium | opus |
| Repair | high | opus |
