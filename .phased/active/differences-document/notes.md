
## Phase 1

- Rows re-verified by eight read-only agents, one per area, against HEAD fbe0b45; each self-checked refs and cell format, then the contract checker ran on the assembled file.
- A7.24 (CHECK constraint) is kept, not deleted: the plan's example assumed it was removed, but `constraint(constraint_type='CHECK')` is still declared (src/asqueel/elements.py:72) and projected (src/asqueel/migration.py:246-251); a PostgreSQL proof plans it. The row cites the user decision that removes it, not yet applied.
- A2.24 (record refresh) stays as `mancante-eliminata` rather than in Righe tolte: the plan names `record.refresh()` as the example of that state; Funzione now describes the legacy cached record.
- A3.15 and A3.18 each mixed a realised and a deferred feature; split so each row has one Stato (new A3.25 variant columns, A3.24 #PREF).
- A1.27 sqldefault/extra_sql/generated_expression: `diverso`, not `nuovo` — the legacy migrator reads them (gnrsqlmigration/structures.py:68-69).
- A5.21 batchUpdate kept `mancante-temporanea` (high level, later), with `query().update()` as its own `nuovo` row A5.31; A5.20 deleteSelection is `mancante-sostituita` by `query().delete()` as the plan states.
- Code that contradicts a recorded user decision, reported in the rows: `update()` ignores storename and extra kwargs (A5.2); X projected as text on SQLite (A8.22); TSV on SQLite gives KeyError (A7.21); legacy adapters raise ModuleNotFoundError (A8.23).
- Guide pages contradicting the code (Phase 2 must follow the code, not them): docs/guide/queries.md (limit=0, default order, auto names), docs/guide/limitations.md, docs/guide/sqlite.md:81-82 (ILIKE), docs/guide/environment.md:78-82, docs/guide/legacy-features.md section 8.
- Some Motivazione cells cite `decisione utente 2026-10-15/16/18` taken from design docs and earlier plans, not from decisioni.md.

## Phase 2

- The four blocks were written in parallel by four read-only agents (one per block, same brief: card format, checker rules), then assembled with intro, To implement, Migration, API levels and Proposals; the planned batches were not committed separately.
- Cards follow the code where guide pages disagree (already recorded in the inventory): A8.5 ILIKE, A8.21 limit=0, A2.5/A2.11/A2.13/A2.15/A2.16/A2.18 queries.md, A5.9 hooks.md `level`, A5.16 RETURNING on SQLite, A3.12 pyColumn message.
- A5.2: the card describes the code (storename and extra kwargs accepted and ignored), which contradicts the recorded decision to raise.
- A1.10: table-level `variant`/`mixin` errors print `app.None:` instead of the table name; the card quotes only the column example.
- A4.6: the `'C'` → `'c'` proof holds for `onDelete_sql`; `onDelete='C'` is rejected by the validator. Card uses `onDelete_sql`.
- A5.26 and some GenroPy snippets are illustrative, built on legacy signatures at 95da66ee, not taken from a test.
- docs/guide/legacy.md link text follows the new title.
