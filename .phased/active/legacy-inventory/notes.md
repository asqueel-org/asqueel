## Phase 1

- Features that cross areas appear once: `*` forms in A2.3, many paths in A4.9, joinConditions/relationDict in A4.13-A4.14, joinColumn in A4.11, alias relation inheritance in A4.21, #ENV/#PREF in A3.18, `nome::dtype` (physical and virtual) in A1.6. Later phases reference these IDs instead of adding rows.
- `diverso` rows whose difference has no recorded reason (A1.5, A1.11, A1.13, A1.19, A1.22) cite the public doc that describes the asqueel side (docs/design/42-configuration-grammar.md, docs/guide/troubleshooting.md) and say "nessuna motivazione registrata". The checker requires a source; inventing a reason was rejected.
- Code contradicts public docs in several places (the rows say so; the code wins): docs/guide/queries.md:149, :355-363, :458-464, :124; docs/guide/limitations.md:23, :237, :247, :248; docs/guide/models.md:105; docs/guide/formulas.md:66-67, :239-240. Phase 3 must describe the code, not those pages.
- `_check_macros` (src/asqueel/compiler.py:517-519) reports every unported macro (#ENV, #PREF, #BAG, #TSQUERY) as "Hierarchical macro expansion is not connected yet" (row A3.18).
- Asqueel revision cited in `## Fonti`: 4361e769a53148c83a527fa1afa02dd2ac796668 (HEAD at phase start).
