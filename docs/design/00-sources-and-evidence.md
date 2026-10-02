# 00 — Fonti, baseline e verifiche

## Baseline

| ID | Fonte | Perimetro |
|---|---|---|
| S01 | asqueel `adba5d52174d166c59b4b364c9721b2e92837c5c` | Package canonico attuale: builder, elementi, catalogo, validatori, reader, emitter e proiezione migration. |
| S02 | Genropy legacy `e12f2ce54245e57e48371ae0f47e928e0d55b960` | Sorgenti letti dal riferimento develop, non dal checkout legacy locale più vecchio. |
| S03 | Builders 0.27.0 e documentazione Configuration consultata | Montaggio di sotto-grammatiche e composizione delle ricette. |
| S04 | asqueel-migration locale `2f9b965314d71915afbac79a40960c0c65462d31` | Ispezione di strutture, validazione e handler degli event trigger. Nessun collaudo completo nuovo di questo checkout. |
| S05 | asqueel-migration `e64fa00b22b304263f515765bb44e5b74d9e9534` | Versione fissata nei precedenti test d'integrazione; non va confusa con S04. |
| S06 | GEP 1, GEP 2 e discussione virtualRelation | Proposte e intenzioni; non prove di codice consegnato. |
| S07 | Conversazioni SQL/Builders di luglio e settembre reperite | Contesto delle scelte, ricostruito nel rapporto storico. |
| S08 | Indicazioni dell'utente in questa conversazione | Obiettivi e vincoli del progetto moderno. |
| S09 | Documentazione PostgreSQL 18 consultata | Semantica delle primitive native; non scelta della versione minima del prodotto. |

Root verificabili dei sorgenti:

- [asqueel S01](https://github.com/asqueel-org/asqueel/tree/adba5d52174d166c59b4b364c9721b2e92837c5c).
- [Genropy S02](https://github.com/genropy/genropy/tree/e12f2ce54245e57e48371ae0f47e928e0d55b960/gnrpy).
- [Migratore S05](https://github.com/asqueel-org/asqueel-migration/tree/e64fa00b22b304263f515765bb44e5b74d9e9534).
- [GEP e discussione virtualRelation](https://github.com/genropy/genropy_meta/issues/1).

Quando un finding cita `S02:gnrsqldata/compiler.py`, il percorso completo è
`gnrpy/gnr/sql/gnrsqldata/compiler.py`. Per S01 e S04 i percorsi iniziano nella
rispettiva directory `src`. Il metodo/classe citato permette di localizzare
l'evidenza senza dipendere da numeri di riga di un branch mobile.

## Classificazione delle evidenze

| Sigla | Significato |
|---|---|
| COD | Osservato nel codice della baseline; non implica esecuzione end-to-end. |
| PRO | Verificato da una prova mirata locale, con perimetro esplicito. |
| PRE | Risultato di verifiche precedenti documentate, non rieseguite per questo dossier. |
| DIS | Esposto in conversazione/GEP/issue; distinguere proposta e riproduzione altrui. |
| INF | Deduzione tecnica dalle fonti; richiede la prova indicata. |

«Non presente nella superficie esaminata» non significa «impossibile in ogni
branch o applicazione». Il dossier non inventaria tutte le installazioni GenroPy.

## Verifiche effettivamente disponibili

1. Sei file centrali legacy confrontati byte per byte con S02: compiler,
   compiler_next, query, record, model e selection.
2. Uguaglianza compiler/compiler_next verificata con la normalizzazione del
   test upstream: docstring del modulo, nome della classe e righe vuote esclusi.
3. Prototipo Builders 0.27 con due montaggi annidati: percorso
   `db.schemas.public.tables.invoice.columns.id` conservato.
4. Sedici risultati numerici del dataset del corpus verificati con SQL diretto
   su SQLite in memoria. Non è stato eseguito un compiler GenroPy in questa prova.
5. Precedenti verifiche S01/S05: 122 passati e 2 xfail nella suite con PostgreSQL,
   più profili core/Routes/ASGI, packaging, Ruff e mypy. Si vedano risultati e
   limitazioni nel [rapporto](../ecosystem-alignment.md).

## Cosa non è certificato

- Equivalenza completa del compiler nuovo: non è stato implementato.
- Correttezza di tutti i comportamenti legacy descritti: alcuni test upstream
  verificano solo tipo del risultato o count positivo.
- Prestazioni dei piani proposti, concorrenza, streaming e bulk.
- Importazione completa di una vera applicazione con tutti i suoi hook.
- Migrazione end-to-end di view/funzioni/trigger/partizioni fisiche.
- Risoluzione dei difetti upstream S05 in versioni successive: va verificata
  aggiornando la baseline, non inferita dal solo SHA differente di S04.

Il checkout locale del migratore contiene inoltre un file non tracciato
`PATTERNS_DISABLED`, non modificato per questa analisi. Non è stato usato come
evidenza di comportamento o come configurazione da adottare.

## Documentazione PostgreSQL di riferimento

[INSERT](https://www.postgresql.org/docs/18/sql-insert.html),
[COPY](https://www.postgresql.org/docs/18/sql-copy.html),
[view](https://www.postgresql.org/docs/18/sql-createview.html),
[funzioni](https://www.postgresql.org/docs/18/sql-createfunction.html),
[trigger](https://www.postgresql.org/docs/18/trigger-definition.html),
[partizioni](https://www.postgresql.org/docs/18/ddl-partitioning.html),
[RLS](https://www.postgresql.org/docs/18/ddl-rowsecurity.html),
[LATERAL e join](https://www.postgresql.org/docs/18/queries-table-expressions.html),
[CTE](https://www.postgresql.org/docs/18/queries-with.html),
[EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html).
