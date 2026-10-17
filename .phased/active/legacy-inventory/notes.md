## Phase 1

- Features that cross areas appear once: `*` forms in A2.3, many paths in A4.9, joinConditions/relationDict in A4.13-A4.14, joinColumn in A4.11, alias relation inheritance in A4.21, #ENV/#PREF in A3.18, `nome::dtype` (physical and virtual) in A1.6. Later phases reference these IDs instead of adding rows.
- `diverso` rows whose difference has no recorded reason (A1.5, A1.11, A1.13, A1.19, A1.22) cite the public doc that describes the asqueel side (docs/design/42-configuration-grammar.md, docs/guide/troubleshooting.md) and say "nessuna motivazione registrata". The checker requires a source; inventing a reason was rejected.
- Code contradicts public docs in several places (the rows say so; the code wins): docs/guide/queries.md:149, :355-363, :458-464, :124; docs/guide/limitations.md:23, :237, :247, :248; docs/guide/models.md:105; docs/guide/formulas.md:66-67, :239-240. Phase 3 must describe the code, not those pages.
- `_check_macros` (src/asqueel/compiler.py:517-519) reports every unported macro (#ENV, #PREF, #BAG, #TSQUERY) as "Hierarchical macro expansion is not connected yet" (row A3.18).
- Asqueel revision cited in `## Fonti`: 4361e769a53148c83a527fa1afa02dd2ac796668 (HEAD at phase start).

## Phase 2

- `## Riepilogo` is a bullet list, not a table: the checker reads every `|` line after `## 8 Dialetti` as an area-8 row, so a summary table would break it.
- Decisions recorded only in the private write-cycle plan carry their real date: most are `decisione utente 2026-10-15`, a few `2026-10-16`. The plan said 2026-10-16 for all; the recorded date was kept.
- `genropy#n` in rows (#1621, #1686-#1692, #1696) are issues of the genropy repository, not of asqueel. Phases 3-4 must not link them as asqueel issues; A6.25 is `mancante` with `nessuna issue` and mentions genropy#1692 only as context.
- Overlaps resolved: RETURNING is row A5.16 (PostgreSQL and SQLite: SqliteDialect inherits the capabilities); A8.13 is only the SQLite 3.35 minimum. A2.11 says limit/offset `presente`; A8.21 records the difference for limit=0 and OFFSET without LIMIT on SQLite. Phase 1 rows were not edited.
- Decision vs code: the 2026-10-16 SQLite decision (deferred transaction, lock only with for_update) is not what the code does: src/asqueel/drivers/sqlite.py:64-65 opens BEGIN IMMEDIATE for every unit of work (A6.27). The row describes the code.
- Code contradicts public docs (code wins, rows say so): docs/guide/writes.md:48-49 and docs/guide/limitations.md:74-75 (SQLite has RETURNING); docs/guide/sqlite.md:65 (ILIKE is translated); docs/guide/limitations.md:20 (ILIKE, ~*, IS TRUE translated on SQLite); docs/guide/cheatsheet.md:87; docs/guide/hooks.md:70-71 (no `level` field); docs/guide/environment.md:101-103 (missing :env_* compiles to None); docs/adattamenti-legacy.md:48-97 and :75-78 (old write layer); docs/design/42-configuration-grammar.md:671 and :526-527. Phase 3 describes the code, not these pages.
- WriteCompiler.lock_table (src/asqueel/write_compiler.py:176) has no caller in src: a project cannot lock a table (A6.25).

## Phase 3

- Every item carries its inventory ID `(A<n>.<m>)`, `presente` rows included, so coverage is checkable by regex; the page names the inventory path as plain text, not as a link.
- The workaround of a `mancante` item is the inventory's "leave it out" alternative (c); the other alternatives stay out of the page, as decided.
- Reasons recorded as "nessuna motivazione registrata" read "not recorded". Reasons citing a user decision read "decision of <date>"; genropy#n issues are described, never linked.
- Issues cited in `diverso`/`nuovo` rows (#3, #15, #16, #19, #21, #22, #23, #25, #26) are linked too.

## Phase 4

- The page is generated from the inventory by a throwaway script (not committed): rows are copied, not rewritten, so the page adds no claim.
- The old page is dated 4 October 2026 in its header and was committed on 5 October 2026; the new header names both dates.
- Google Fonts link of the old page dropped to keep the page self-contained; the font stacks fall back to system fonts.
- Only plain `#n` is linked to asqueel issues; `genropy#n` stays unlinked text.
