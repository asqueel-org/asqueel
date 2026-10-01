# 31 — Matrice dei contratti query: collezioni, DISTINCT, GROUP BY/HAVING, count

Stato: evidenza del passo 1 del [piano 30](30-query-completion-plan.md).
Nessuna modifica a `src/asqueel`. Le decisioni aperte attendono la decisione dell'utente.
Riferimento legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.

## Fonti delle prove

| File | Contenuto |
|---|---|
| `evidence/query_completion_probes.json` | Comportamento attuale di Asqueel (fase 1). Chiavi `<caso>_pg` / `<caso>_sqlite`. |
| `evidence/query_benchmark.json` | Baseline delle prestazioni (fase 1). Non citato dalle righe. |
| `evidence/query_legacy_oracle.json` | Oracolo legacy (questo documento). Chiavi `legacy_<caso>_pg` / `legacy_<caso>_sqlite`. |

Rigenerazione dell'oracolo:

```
python docs/design/evidence/query_legacy_oracle.py <radice legacy> --dsn <db usa e getta> --output <file>.json
```

Lo script verifica la revisione legacy e l'assenza di modifiche locali in
`gnrpy/gnr/sql`. Registra lo sha256 di ogni file legacy letto. Crea ed elimina
un proprio schema PostgreSQL. Usa SQLite in memoria.

I percorsi legacy abbreviati sono relativi a `gnrpy/gnr/sql/`:

- `gnrpostgres3.py`, `_gnrbaseadapter.py`, `gnrsqlite.py`: `adapters/`.
- `compiler.py`, `query.py`: `gnrsqldata/`.
- `execute.py`: `gnrsql/`.

## Metodo e limiti dell'oracolo

Ogni voce dell'oracolo dichiara `method`:

- `executed-extracted`: tutto il percorso è codice legacy estratto per AST ed
  eseguito. Vale per lo SQL diretto (`db.execute`).
- `derived-from-source`: `SqlQueryCompiler.compiledQuery` non è eseguibile fuori
  dal framework. I frammenti SQL che produrrebbe sono scritti a mano dalle righe
  citate nel campo `derivation`. Il resto è codice legacy eseguito:
  `compileSql`, `ExecuteMixin.execute`, `prepareSqlText`, `adaptTupleListSet`,
  `GnrDictCursor.execute`, `SqlQuery.cursor`, `SqlQuery.count`.

Limiti dichiarati:

- La correlazione `#THIS` della sottoquery è scritta nella forma risolta `"t0"."id"`.
- `GnrNamedList` è sostituita da `list`. I cursori base psycopg/sqlite3 sono
  sottoclassati solo per registrare SQL e parametri inviati (`sent_sql`, `sent_params`).
- SQLite usa il cursore standard di sqlite3, non `GnrSqliteCursor` (che registra
  log e riconverte i valori `str`), né le opzioni di `connect` legacy.
- `sql_audit`, i callback deferred e `table().use_dbstores` sono no-op.
- Nessun codice di applicazione, trigger, package, store o locale è eseguito.

Dataset dell'oracolo (`dataset` nel JSON). Fatture: `id, customer_id, total, __del_ts`.

| id | customer_id | total | cancellata |
|---|---|---|---|
| 10 | 1 | 125.00 | no |
| 11 | 2 | 40.00 | no |
| 12 | 1 | 15.50 | no |
| 13 | NULL | 7.00 | no |
| 14 | 2 | 40.00 | sì (`__del_ts` valorizzato) |
| 15 | 3 | 40.00 | no |

La tabella legacy dichiara `__del_ts` come campo di cancellazione logica. Senza
`excludeLogicalDeleted='mark'` ogni query riceve `("t0"."__del_ts" IS NULL)`
(`compiler.py:981`). Righe visibili: 10, 11, 12, 13, 15.
I risultati attesi del contratto proposto si riferiscono a questo dataset.
Le probe Asqueel della fase 1 usano un dataset diverso (fatture 10–13).

## Osservazione trasversale: valori nel testo SQL

Il legacy PostgreSQL (`gnrpostgres3.py:346`) inserisce i valori nel testo SQL
lato client con `sql.SQL(query).format(**params)`. Lo `sent_sql` delle voci `_pg`
contiene quindi i valori letterali e `sent_params` è `null`. Il legacy SQLite
invia segnaposto `:nome` con parametri. Asqueel invia sempre parametri al driver.
Il piano 30 (riga 83) esclude l'interpolazione: ogni contratto sotto usa binding.

## Stato delle righe

- `settled`: fissato da `05-decisions.md`, dall'handoff, o da una prescrizione
  esplicita del piano 30, il piano richiesto dall'utente che l'handoff indica
  come riferimento. La riga cita la fonte.
- `open`: richiede una decisione dell'utente. La riga rimanda alla sezione
  «Decisioni aperte».
- `deferred`: fuori dalla chiusura di questo incremento (piano 30, righe 15–19);
  l'interazione è registrata.

## Matrice

### IN / NOT IN

Forma comune legacy (query compilata): `where='$col IN :p'`, colonne `$id`,
`order_by='$id'`. SQL legacy:
`SELECT "t0"."id" AS "id", "t0"."id" AS "pkey" FROM <invoice> AS t0 WHERE (<cond>) AND ("t0"."__del_ts" IS NULL) ORDER BY "t0"."id"`.
L'espansione avviene in `prepareSqlText`, chiamato da `execute.py:121` su ogni
testo SQL: `gnrpostgres3.py:74` (PostgreSQL), `_gnrbaseadapter.py:208` (SQLite).

Comportamento attuale Asqueel per ogni forma `IN :p`: il compiler emette un solo
segnaposto per nome (`src/asqueel/compiler.py:152`), qualunque sia il tipo del
valore. Le probe `in_list_*` e `not_in_list_*` coprono quindi tutte le righe di
questa sezione prive di probe dedicata. Esito: PostgreSQL `syntax error at or near "$1"`,
SQLite `near ":ids": syntax error`.

#### R01 — lista

- Legacy: `gnrpostgres3.py:94`, `_gnrbaseadapter.py:215`. `ids=[10, 11]`.
  PostgreSQL invia `"t0"."id" IN(10, 11)`. SQLite invia `IN (:ids0,:ids1)`
  con `{ids0: 10, ids1: 11}`. Risultato: 10, 11 su entrambi.
  Prova: `legacy_in_list_pg`, `legacy_in_list_sqlite`.
- Asqueel: `in_list_pg`, `in_list_sqlite` (errore).
- Contratto: `"t0"."id" IN (<p1>, <p2>)`, un segnaposto per elemento, valori
  nei parametri. Risultato: 10, 11. Stesso esito su PostgreSQL e SQLite.
- Stato: `settled` — piano 30 riga 82–83.

#### R02 — NOT IN lista

- Legacy: `gnrpostgres3.py:94`. `ids=[10, 11]`. PostgreSQL invia
  `"t0"."id" NOT IN(10, 11)`. Risultato: 12, 13, 15 su entrambi.
  Prova: `legacy_not_in_list_pg`, `legacy_not_in_list_sqlite`.
- Asqueel: `not_in_list_pg`, `not_in_list_sqlite` (errore).
- Contratto: `"t0"."id" NOT IN (<p1>, <p2>)`. Risultato: 12, 13, 15.
- Stato: `settled` — piano 30 riga 82–83.

#### R03 — tupla

- Legacy: `gnrpostgres3.py:77–79` converte in lista; `_gnrbaseadapter.py:214`
  accetta `tuple`. `ids=(10, 11)`. Risultato: 10, 11 su entrambi.
  Prova: `legacy_in_tuple_pg`, `legacy_in_tuple_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore).
- Contratto: identico a R01.
- Stato: `settled` — piano 30 riga 44 e 82.

#### R04 — set

- Legacy: `gnrpostgres3.py:77`, `_gnrbaseadapter.py:214` accettano `set`.
  L'ordine dei segnaposto segue l'iterazione del set. `ids={10, 11}`.
  Risultato: 10, 11 su entrambi. Prova: `legacy_in_set_pg`, `legacy_in_set_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore).
- Contratto proposto: identico a R01; l'ordine dei segnaposto non cambia il risultato.
- Stato: `open` — decisione D7.

#### R05 — collezione vuota

- Legacy PostgreSQL: `gnrpostgres3.py:81` riscrive `<alias>.<col> IN :ids` in
  `FALSE`, solo se la colonna ha la forma `"tN"."col"`. Invia `WHERE (FALSE) AND (...)`.
  Risultato: nessuna riga. Legacy SQLite: `_gnrbaseadapter.py:215` produce
  `IN ()`, valido solo in SQLite. Risultato: nessuna riga.
  Prova: `legacy_in_empty_pg`, `legacy_in_empty_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore); `any_empty_pg` per `= ANY`
  (nessuna riga).
- Contratto: nessun `IN ()` nel testo. Il predicato diventa falso
  (`FALSE` PostgreSQL, `0` SQLite o forma equivalente). Risultato: nessuna riga.
- Stato: `settled` — piano 30 riga 84.

#### R06 — NOT IN con collezione vuota

- Legacy PostgreSQL: `gnrpostgres3.py:82` riscrive in `TRUE`. Risultato: 10, 11,
  12, 13, 15. Legacy SQLite: `NOT IN ()`, risultato identico.
  Prova: `legacy_not_in_empty_pg`, `legacy_not_in_empty_sqlite`.
- Asqueel: `not_in_list_pg` (stesso percorso, errore).
- Contratto proposto: predicato vero, nessun `NOT IN ()`. Risultato: 10, 11, 12, 13, 15,
  incluse le righe con colonna NULL.
- Stato: `open` — decisione D3.

#### R07 — duplicati

- Legacy: i duplicati restano nella lista (`gnrpostgres3.py:85`, `_gnrbaseadapter.py:215`).
  PostgreSQL invia `IN(10, 10, 11)`.
  Risultato: 10, 11 su entrambi. Prova: `legacy_in_duplicates_pg`, `legacy_in_duplicates_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore).
- Contratto: un segnaposto per elemento, duplicati inclusi, nessuna deduplicazione.
  Risultato: 10, 11.
- Stato: `settled` — piano 30 riga 82 (binding dei singoli valori); il risultato
  non dipende dai duplicati.

#### R08 — None nella collezione

- Legacy: `None` diventa `NULL` (`gnrpostgres3.py:85` espande, `gnrpostgres3.py:346`
  rende il letterale). `ids=[10, None]`: PostgreSQL invia `IN(10, NULL)`,
  risultato 10. `NOT IN` con `[10, None]`: nessuna riga (logica a tre valori SQL).
  Identico su SQLite. Prova: `legacy_in_none_member_pg`, `legacy_in_none_member_sqlite`,
  `legacy_not_in_none_member_pg`, `legacy_not_in_none_member_sqlite`.
- Asqueel: `in_list_pg` (errore); `any_none_member_pg` per `= ANY` (risultato 10).
- Contratto proposto: `None` legato come NULL, semantica SQL. `IN` → 10;
  `NOT IN` → nessuna riga.
- Stato: `open` — decisione D6.

#### R09 — colonna con valore NULL

- Legacy (`gnrpostgres3.py:94`, `_gnrbaseadapter.py:215`): `$customer_id IN :ids`
  con `[1, 2]` → 10, 11, 12 (la fattura 13 esclusa).
  `$customer_id NOT IN :ids` con `[1]` → 11, 15 (la 13 esclusa). Identico su
  entrambi. Prova: `legacy_in_null_column_pg`, `legacy_not_in_null_column_pg`,
  `legacy_in_null_column_sqlite`, `legacy_not_in_null_column_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore).
- Contratto proposto: semantica SQL; una colonna NULL non soddisfa né `IN` né
  `NOT IN` con collezione non vuota.
- Stato: `open` — decisione D6.

#### R10 — stringa scalare

- Legacy: una stringa non è una collezione (`gnrpostgres3.py:77`) e resta un
  valore singolo. `$note IN :notes` con `'First order'`: PostgreSQL invia
  `IN 'First order'` → `syntax error at or near "'First order'"`. SQLite:
  `near ":notes": syntax error`. Prova: `legacy_in_scalar_string_pg`,
  `legacy_in_scalar_string_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore SQL).
- Contratto: errore esplicito di Asqueel prima dell'esecuzione, che nomina il
  parametro. Nessuna conversione in lista di caratteri, nessun SQL inviato.
- Stato: `settled` — piano 30 riga 45–46. Il legacy fallisce anch'esso.

#### R11 — stesso parametro usato due volte

- Legacy: `$id IN :ids OR $customer_id IN :ids` con `[1, 11]`. Ogni occorrenza
  è espansa con gli stessi valori. Risultato: 10, 11, 12 su entrambi.
  Prova: `legacy_same_param_twice_pg`, `legacy_same_param_twice_sqlite`.
- Legacy, stesso parametro in posizione `IN` e scalare: `$id IN :ids OR $id = ANY(:ids)`.
  PostgreSQL: `KeyError: 'ids'` (`gnrpostgres3.py:86` rimuove il parametro
  originale). SQLite: `no such function: ANY`. Prova: `legacy_same_param_in_and_any_pg`,
  `legacy_same_param_in_and_any_sqlite`.
- Asqueel: `in_list_pg` (errore); `any_list_pg` (= ANY funziona su PostgreSQL).
- Contratto: due occorrenze `IN` espanse con gli stessi valori, risultato 10, 11, 12.
  Uso misto `IN` e scalare dello stesso parametro: errore esplicito prima dell'esecuzione.
- Stato: `settled` — piano 30 riga 87 e 91.

#### R12 — due collezioni nella stessa query

- Legacy: `$id IN :ids AND $customer_id NOT IN :customers` con `[10, 11, 12]` e `[2]`.
  Risultato: 10, 12 su entrambi. Prova: `legacy_two_collections_pg`, `legacy_two_collections_sqlite`.
- Difetto legacy con nomi a prefisso comune: `:ids` e `:ids2`.
  PostgreSQL (`gnrpostgres3.py:94`, la regex di `ids` cattura anche `:ids2`):
  `syntax error at or near "2"`. SQLite (`_gnrbaseadapter.py:217`): il nome
  generato `ids2` sovrascrive il parametro `ids2`. Risultato errato 10 invece di 10, 12.
  Prova: `legacy_two_collections_prefix_pg`, `legacy_two_collections_prefix_sqlite`.
- Asqueel: `in_list_pg` (stesso percorso, errore).
- Contratto: ogni collezione espansa in modo indipendente. I nomi generati non
  collidono con nessun parametro esistente. Risultato: 10, 12 per entrambe le query.
- Stato: `settled` — piano 30 riga 86–87. Il difetto legacy non è un requisito
  (piano 30 riga 25).

#### R13 — dentro una sottoquery nominata

- Legacy: formula `select=` su `customer`; alias della sottoquery `t0_t0`
  (`compiler.py:416`), testo racchiuso da `compiler.py:409` e `:439`. La regex
  di `gnrpostgres3.py:81` riconosce `"t0_t0"."id"`. `ids=[10, 11, 14]` →
  conteggi 1, 2, 0 per i clienti 1, 2, 3 (la sottoquery non esclude i cancellati,
  `compiler.py:414`). Collezione vuota → `FALSE` dentro la sottoquery, conteggi 0, 0, 0.
  Identico su SQLite (`IN ()`). Prova: `legacy_subquery_in_list_pg`,
  `legacy_subquery_in_empty_pg`, `legacy_subquery_in_list_sqlite`, `legacy_subquery_in_empty_sqlite`.
- Asqueel: `in_list_pg` (le sottoquery usano lo stesso `binding`, `src/asqueel/compiler.py:152`).
- Contratto: espansione e collezione vuota come R01 e R05, dentro la sottoquery.
  Nomi generati senza collisione con i parametri della query esterna.
- Stato: `settled` — piano 30 riga 89.

#### R14 — SQL diretto (`db.execute(sql, params)`)

- Legacy: `execute.py:121` chiama `prepareSqlText` su ogni testo, anche diretto.
  `SELECT id FROM <invoice> WHERE id IN :ids ORDER BY id` con `[10, 11]` → 10, 11
  su entrambi. Con `[]`: PostgreSQL non riscrive (la colonna `id` non ha la forma
  `"tN"."col"` richiesta da `gnrpostgres3.py:81`), invia `IN '{}'` →
  `syntax error at or near "'{}'"`. SQLite invia `IN ()` → nessuna riga.
  Prova: `legacy_direct_in_list_pg`, `legacy_direct_in_empty_pg`,
  `legacy_direct_in_list_sqlite`, `legacy_direct_in_empty_sqlite`.
- Asqueel: `src/asqueel/drivers/sql.py:42` emette un segnaposto per nome, come
  il compiler. Probe più vicina: `in_list_pg`.
- Contratto proposto: vedi D2.
- Stato: `open` — decisione D2.

### DISTINCT

Asqueel attuale: l'opzione `distinct` è rifiutata qualunque sia il valore
(`src/asqueel/application_table.py:35`). Probe: `option_distinct_pg`,
`option_distinct_sqlite`. Asqueel non aggiunge colonne implicite
(`docs/guide/limitations.md:189`).

#### R15 — `distinct=True`

- Legacy: `compiler.py:1057` → `SELECT DISTINCT`. `compiler.py:902` marca la
  query come aggregata: nessuna colonna pkey, nessun ordine di tabella
  (`compiler.py:910`). Colonne `$total`: risultato 7.00, 15.50, 40.00, 125.00
  (4 righe). Prova: `legacy_distinct_true_pg`, `legacy_distinct_true_sqlite`.
- Contratto: `SELECT DISTINCT <proiezione richiesta>`, senza colonne aggiunte.
  Risultato: 4 righe.
- Stato: `settled` — piano 30 riga 111–112.

#### R16 — `distinct=''`

- Legacy: `compiler.py:899` → nessun DISTINCT. Colonna pkey aggiunta
  (`compiler.py:947`). DISTINCT automatico solo con join to-many
  (`compiler.py:1058`), fuori perimetro. Risultato: 5 righe con pkey.
  Prova: `legacy_distinct_empty_pg`, `legacy_distinct_empty_sqlite`.
- Contratto proposto: vedi D5.
- Stato: `open` — decisione D5.

#### R17 — `distinct=None`

- Legacy: default di `SqlQuery` (`query.py:144`); stesso SQL e risultato di R16.
  Prova: `legacy_distinct_none_pg`, `legacy_distinct_none_sqlite`.
- Contratto proposto: vedi D5.
- Stato: `open` — decisione D5.

#### R18 — DISTINCT con `order_by` fuori dalla proiezione

- Legacy: colonne `$customer_id`, `order_by='$total'`. Le colonne nascoste
  `__ord_col_N` sono aggiunte solo con DISTINCT automatico (`compiler.py:1071`).
  PostgreSQL: `for SELECT DISTINCT, ORDER BY expressions must appear in select list`.
  SQLite: esegue (risultato NULL, 2, 3, 1). Prova:
  `legacy_distinct_order_by_outside_projection_pg`, `legacy_distinct_order_by_outside_projection_sqlite`.
- Contratto: errore esplicito di Asqueel su entrambi i backend, prima dell'esecuzione.
- Stato: `settled` — decisione D10 dell'utente (piano 30 riga 66–67).

### GROUP BY e HAVING

Asqueel attuale: `group_by` e `having` sono rifiutati
(`src/asqueel/application_table.py:35`). Probe: `option_group_by_*`,
`option_having_*`, `option_having_only_*`.

#### R19 — GROUP BY

- Legacy: colonne `$customer_id, SUM($total) AS total_sum`, `group_by='$customer_id'`.
  Nessuna colonna pkey (`compiler.py:902`). L'alias esplicito resta non quotato
  (`compiler.py:1018`). Risultato: (1, 140.50), (2, 40.00), (3, 40.00), (NULL, 7.00).
  Il gruppo NULL è ultimo su PostgreSQL e primo su SQLite (ordinamento nativo).
  Prova: `legacy_group_by_pg`, `legacy_group_by_sqlite`.
- Contratto: `GROUP BY "t0"."customer_id"` con riferimenti risolti come nel WHERE.
  Quattro gruppi, incluso NULL. La posizione del gruppo NULL con `order_by` segue
  il backend ed è registrata, non uniformata.
- Stato: `settled` — piano 30 riga 110 e 115.

#### R20 — `group_by='*'`

- Legacy: `compiler.py:906` azzera `group_by` dopo aver marcato la query come
  aggregata. Effetto: niente GROUP BY e niente colonna pkey. Colonne
  `SUM($total) AS total_sum, COUNT(*) AS n` → una riga (227.50, 5).
  Prova: `legacy_group_by_star_pg`, `legacy_group_by_star_sqlite`.
- Contratto proposto: vedi D4.
- Stato: `open` — decisione D4.

#### R21 — HAVING con parametri

- Legacy: R19 più `having='SUM($total) >= :minimum'`, `minimum=40`
  (`compiler.py:1097`).
  PostgreSQL invia `HAVING SUM("t0"."total") >= 40` (valore nel testo).
  Risultato: clienti 1, 2, 3. Prova: `legacy_having_params_pg`, `legacy_having_params_sqlite`.
- Contratto: `HAVING SUM("t0"."total") >= <p>` con `minimum` nei parametri.
  Risultato: 3 gruppi.
- Stato: `settled` — piano 30 riga 113–114.

#### R22 — proiezione aggregata senza GROUP BY

- Legacy: colonne `SUM($total) AS total_sum`. Senza `distinct` né `group_by` la
  query non è marcata aggregata (`compiler.py:902`). La colonna pkey è aggiunta
  (`compiler.py:947`) prima che `compiler.py:1004` riconosca `SUM(`.
  PostgreSQL: `column "t0.id" must appear in the GROUP BY clause`. SQLite:
  una riga (227.5, 10) con pkey arbitraria. Prova: `legacy_aggregate_without_group_by_pg`,
  `legacy_aggregate_without_group_by_sqlite`.
- Asqueel: nessuna probe dedicata. Asqueel non aggiunge pkey implicita
  (`docs/guide/limitations.md:189`); `count_terminal_pg` indica l'aggregato
  SQL esplicito come alternativa al count.
- Contratto: una riga con i soli valori aggregati richiesti: `total_sum = 227.50`.
  Nessuna colonna aggiunta. Stesso esito sui due backend.
- Stato: `settled` — piano 30 riga 25 (difetto legacy non requisito) e riga 43.

### count

Asqueel attuale: `SqlQuery.count()` solleva `UnsupportedFeatureError`
(`src/asqueel/application_table.py:145`). Probe: `count_terminal_pg`,
`count_terminal_sqlite`; coprono tutte le righe di questa sezione.

Legacy: `query.py:557` esegue `compileQuery(count=True)`. Con un'unica riga
`gnr_row_count` restituisce il suo valore, altrimenti `len(fetchall())`
(`query.py:585–588`). In modalità count `order_by` è eliminato
(`compiler.py:940`); `limit` e `offset` restano (`compiler.py:1099`).

Contratto comune (handoff righe 97–98, piano 30 riga 126): intero calcolato dal
database, senza scaricare righe o gruppi; `count()` non modifica la query.

#### R23 — query ordinaria

- Legacy: `SELECT count(*) AS "gnr_row_count" ... WHERE (<cancellazione>)`
  (`compiler.py:946`) → 5. Prova: `legacy_count_plain_pg`, `legacy_count_plain_sqlite`.
- Contratto: `SELECT count(*)` sul piano della query, senza colonne. Risultato: 5.
- Stato: `settled` — piano 30 riga 126–127.

#### R24 — query DISTINCT

- Legacy: la proiezione DISTINCT resta (`compiler.py:943`); conta in Python
  le righe scaricate → 4. Prova: `legacy_count_distinct_pg`, `legacy_count_distinct_sqlite`.
- Contratto: `SELECT count(*) FROM (SELECT DISTINCT <proiezione> ...) AS <alias>`.
  Risultato: 4.
- Stato: `settled` — handoff righe 97–98, piano 30 riga 127–128.

#### R25 — query raggruppata con HAVING

- Legacy: la proiezione diventa il `group_by` (`compiler.py:942`); conta in
  Python i gruppi scaricati → 3. Prova: `legacy_count_grouped_having_pg`,
  `legacy_count_grouped_having_sqlite`.
- Contratto: `SELECT count(*) FROM (SELECT ... GROUP BY ... HAVING ...) AS <alias>`,
  con i parametri di HAVING legati. Risultato: 3.
- Stato: `settled` — handoff righe 97–98, piano 30 riga 128.

#### R26 — limit e offset

- Legacy (`compiler.py:1099`, `query.py:587`), query ordinaria: `limit=2` →
  `count(*) ... LIMIT 2` → 5 (limit senza effetto). `limit=2, offset=2` → la sola riga del conteggio è saltata → 0.
  Legacy, DISTINCT: `limit=2, offset=1` → 2 (dimensione della pagina).
  Legacy, raggruppata: `limit=2` → 2. Identico su entrambi i backend.
  Prova: `legacy_count_limit_pg`, `legacy_count_limit_offset_pg`,
  `legacy_count_distinct_limit_offset_pg`, `legacy_count_grouped_limit_pg` e
  le corrispondenti `_sqlite`.
- Contratto proposto: vedi D1.
- Stato: `open` — decisione D1.

#### R27 — dataset vuoto

- Legacy (`query.py:587`): query ordinaria con `$id < 0` → 0 (una riga
  `gnr_row_count = 0`).
  Raggruppata → 0 (nessun gruppo). Prova: `legacy_count_empty_pg`,
  `legacy_count_grouped_empty_pg` e le corrispondenti `_sqlite`.
- Contratto: 0 per ogni forma.
- Stato: `settled` — piano 30 riga 127–128.

### Interazioni

#### R28 — `for_update` con DISTINCT

- Legacy: `_gnrbaseadapter.py:721` aggiunge `FOR UPDATE OF t0`. PostgreSQL:
  `FOR UPDATE is not allowed with DISTINCT clause`. SQLite: `gnrsqlite.py:140`
  non produce nulla, la query esegue. Prova: `legacy_for_update_distinct_pg`,
  `legacy_for_update_distinct_sqlite`.
- Asqueel: `option_distinct_pg` (rifiuto dell'opzione, prima di `for_update`).
- Contratto: errore esplicito di Asqueel su entrambi i backend, prima dell'esecuzione.
- Stato: `settled` — piano 30 riga 65–67.

#### R29 — `for_update` con GROUP BY

- Legacy (`_gnrbaseadapter.py:721`, `gnrsqlite.py:140`): PostgreSQL
  `FOR UPDATE is not allowed with GROUP BY clause`; SQLite esegue. Prova: `legacy_for_update_group_by_pg`, `legacy_for_update_group_by_sqlite`.
- Asqueel: `option_group_by_pg`.
- Contratto: errore esplicito su entrambi i backend, prima dell'esecuzione.
- Stato: `settled` — piano 30 riga 65–67.

#### R30 — `exclude_logical_deleted='mark'` con aggregati

- Legacy: in modalità `mark` manca la condizione `IS NULL` (`compiler.py:981`) e
  la colonna `_isdeleted` è omessa con aggregati o count (`compiler.py:983`).
  GROUP BY per cliente include la fattura cancellata 14: cliente 2 = 80.00.
  Prova: `legacy_mark_aggregate_pg`, `legacy_mark_aggregate_sqlite`.
- Legacy, count con `mark`: nessuna condizione → 6 (cancellate incluse).
  Prova: `legacy_count_mark_pg`, `legacy_count_mark_sqlite`.
- Asqueel: `option_group_by_pg` (rifiuto prima delle policy). In `mark` Asqueel
  richiede proiezioni di colonne fisiche (`src/asqueel/compiler.py:307`).
- Contratto proposto, aggregati: vedi D8. Count con `mark` su query non
  aggregata: stesse righe del fetch, cancellate incluse → 6.
- Stato: `open` per gli aggregati (decisione D8); `settled` per il count
  (piano 30 riga 132: count rispetta le policy della query).

#### R31 — `order_by` con count

- Legacy: `compiler.py:940` elimina `order_by` in modalità count.
  `order_by='$total'` → stesso SQL di R23 → 5. Prova: `legacy_count_ordered_pg`,
  `legacy_count_ordered_sqlite`.
- Contratto: nessun `ORDER BY` nello SQL del conteggio. Risultato: 5.
- Stato: `settled` — piano 30 riga 133.

#### R32 — `limit`/`offset` con count

- Legacy: `compiler.py:1099` mantiene `limit`/`offset` nello SQL del conteggio;
  esiti in R26. Prova: `legacy_count_limit_offset_pg`, `legacy_count_limit_offset_sqlite`.
- Asqueel: `count_terminal_pg`, `count_terminal_sqlite` (errore).
- Contratto proposto: vedi D1.
- Stato: `open` — decisione D1.

### Righe rinviate

#### R33 — nome automatico di `@rel.col`

- Legacy: `compiler.py:739` traduce `@customer.name` in `$_customer_name`
  (`colToAs`); `compiler.py:1008` usa il nome dopo `$`. Nome risultante: `_customer_name`.
- Asqueel: `customer_name` (`relation_auto_name_pg`, `relation_auto_name_sqlite`).
  `docs/guide/compiler.md:128` dichiara `_customer_name`; `docs/guide/limitations.md:180–182`
  registra la differenza `customer_name`.
- Nota: le due guide si contraddicono. Il passo 6 del piano 30 aggiorna le guide.
  La classificazione `bug` delle probe `relation_auto_name_*` si riferisce a questa
  contraddizione tra guide, non a un difetto del codice da correggere in questo incremento.
- Stato: `deferred` — alias legacy fuori dalla chiusura (piano 30 righe 17–19).

#### R34 — espansione di `*`

- Legacy: `compiler.py:800` → `table.py:479–490` (`gnrsqlmodel/`): colonne
  fisiche non Bag e colonne virtuali statiche.
- Asqueel: espande anche formule e alias, con il join relativo
  (`star_virtual_columns_pg`, `star_virtual_columns_sqlite`).
- Stato: `deferred` — wildcard fuori dalla chiusura (piano 30 righe 17–19).

### Altri rilievi della fase 1

- Ricompilazione: `SqlQuery.compiled` compila a ogni accesso (`recompilation_pg`).
  Classificata `intentional`. Cache esclusa dall'incremento (issue #3).
- Binding `:env_*`: chiave presente, assente ed esplicita (`env_present_pg`,
  `env_absent_pg`, `env_overridden_pg`). Classificata `intentional`. Il legacy
  risolve `:env_*` da `currentEnv` (`execute.py:92–98`). Chiave assente: il legacy
  lega `None` (`execute.py:93`), Asqueel solleva `Missing query parameter`
  (decisione D9). Un parametro esplicito prevale in entrambi.

## Decisioni aperte

#### D1 — count con limit/offset (R26, R32)

- Caso: `query(limit=2, offset=2).count()` sul dataset dell'oracolo.
- Legacy: incoerente. Query ordinaria: `limit` ignorato (5), `offset ≥ 1` → 0.
  DISTINCT e raggruppata: dimensione della pagina (2).
- Opzioni:
  - (a) count ignora `limit`/`offset`: totale delle righe (5).
  - (b) count rispetta `limit`/`offset`: `count() == len(fetch())` (2 con
    `limit=2, offset=2`), tramite sottoquery.
  - (c) count su una query con `limit` o `offset` solleva un errore esplicito.
- Raccomandazione: (c). Ogni regola unica diverge da almeno una forma legacy.
  Un errore rende visibile la divergenza nel codice portato. Il totale si ottiene
  dalla stessa query senza `limit`/`offset`.

#### D2 — espansione IN nello SQL diretto (R14)

- Caso: `db.execute('SELECT id FROM sales.invoice WHERE id IN :ids', {'ids': [10, 11]})`.
- Legacy: espande ogni `IN :nome` in ogni testo SQL (`execute.py:121`). Con
  collezione vuota fallisce su PostgreSQL e restituisce 0 righe su SQLite.
- Opzioni:
  - (a) espandere `IN :nome` / `NOT IN :nome` anche nello SQL diretto, con lo
    stesso contratto delle query compilate (R01–R12, vuoto incluso).
    `src/asqueel/drivers/sql.py` separa già stringhe, commenti e identificatori quotati.
  - (b) nessuna espansione: lo SQL diretto lega il valore così com'è (array
    PostgreSQL con `= ANY`, errore su SQLite). Documentato come limite.
- Raccomandazione: (a). Il codice legacy che usa `db.execute` con liste continua
  a funzionare, e la collezione vuota diventa corretta su entrambi i backend.

#### D3 — NOT IN con collezione vuota (R06)

- Caso: `$customer_id NOT IN :ids` con `ids=[]`; la fattura 13 ha `customer_id` NULL.
- Legacy: PostgreSQL `TRUE` (13 inclusa); SQLite `NOT IN ()` vero anche per NULL (13 inclusa).
- Opzioni:
  - (a) predicato vero: tutte le righe, NULL incluse (5 righe).
  - (b) `<col> IS NOT NULL`: coerente con `NOT IN` non vuoto, che esclude i NULL (4 righe).
  - (c) errore esplicito.
- Raccomandazione: (a). Coincide con il legacy su entrambi i backend e con la
  semantica nativa di SQLite per `NOT IN ()`.

#### D4 — `group_by='*'` (R20)

- Caso: `columns='SUM($total) AS total_sum', group_by='*'`.
- Legacy: segnala «aggregazione senza GROUP BY» per evitare la colonna pkey e
  l'ordine di tabella (`compiler.py:906`).
- Opzioni:
  - (a) accettare `'*'` come no-op: Asqueel non aggiunge pkey né ordine di
    tabella, quindi la query è identica a R22.
  - (b) rifiutare `'*'` con un errore che rimanda alla proiezione aggregata semplice (R22).
- Raccomandazione: (b). Il piano 30 (riga 48) esclude di promettere una forma
  solo perché il parametro esiste; in Asqueel `'*'` non ha effetto.

#### D5 — `distinct=None` e `distinct=''` (R16, R17)

- Caso: `query(columns='$total', distinct=None)` e `distinct=''`.
- Legacy: entrambi significano «DISTINCT automatico se ci sono join to-many»
  (`compiler.py:1058`); senza join to-many nessun DISTINCT.
- Opzioni:
  - (a) `True` → DISTINCT; `False` e `None` → nessun DISTINCT; ogni altro valore,
    `''` incluso, → errore, come `for_update` (`src/asqueel/compiler.py:604`).
  - (b) tutti i valori falsy legacy (`None`, `''`, `False`) → nessun DISTINCT.
  - (c) solo `bool`; `None` e `''` → errore.
- Raccomandazione: (a). `None` è il default legacy di `SqlQuery` (`query.py:144`).
  Asqueel non ha relazioni to-many, quindi il DISTINCT automatico non esiste.

#### D6 — None nella collezione e colonna NULL (R08, R09)

- Caso: `$id IN :ids` / `NOT IN :ids` con `ids=[10, None]`; `$customer_id NOT IN :ids`
  con la fattura 13 NULL.
- Legacy: semantica SQL a tre valori su entrambi i backend.
- Opzioni:
  - (a) semantica SQL: `None` legato come NULL; `IN` ignora NULL, `NOT IN` con
    NULL nella collezione non restituisce righe; colonne NULL mai soddisfatte.
  - (b) rifiutare `None` nella collezione con errore esplicito.
- Raccomandazione: (a). Coincide con il legacy e con `= ANY` già supportato
  (`docs/guide/limitations.md:186–187`). Va documentata nella guida query.

#### D7 — set come collezione (R04)

- Caso: `ids={10, 11}`.
- Legacy: accettato; ordine dei segnaposto secondo l'iterazione del set.
- Opzioni:
  - (a) accettare `set` e `frozenset`.
  - (b) solo `list` e `tuple`; `set` → errore.
- Raccomandazione: (a). Il risultato non dipende dall'ordine; il legacy lo accetta.

#### D8 — `mark` con aggregati, DISTINCT o GROUP BY (R30)

- Caso: `group_by='$customer_id', exclude_logical_deleted='mark'`.
- Legacy: nessuna condizione e nessun flag; le righe cancellate entrano negli
  aggregati (cliente 2 = 80.00 invece di 40.00).
- Opzioni:
  - (a) comportamento legacy: righe cancellate incluse, nessun `_isdeleted`.
  - (b) errore esplicito: `mark` richiede una proiezione non aggregata.
- Raccomandazione: (b). Coerente con il vincolo attuale di `mark`
  (`src/asqueel/compiler.py:307`). Evita aggregati che includono righe cancellate
  senza segnalarlo. Le righe cancellate restano ottenibili con
  `exclude_logical_deleted=False`.

## Decisioni dell'utente

Decise il 2026-10-01: accettate tutte le raccomandazioni. Le righe `open`
che rimandano a D1–D8 sono da leggere come `settled` secondo questa sezione.

- D1 — (c): `count()` su una query con `limit` o `offset` solleva un errore esplicito.
- D2 — (a): `IN :nome` / `NOT IN :nome` espansi anche nello SQL diretto, con il contratto R01–R12.
- D3 — (a): `NOT IN` con collezione vuota è un predicato vero; righe con colonna NULL incluse.
- D4 — (b): `group_by='*'` rifiutato con un errore che rimanda alla proiezione aggregata (R22).
- D5 — (a): `distinct=True` → DISTINCT; `False` e `None` → nessun DISTINCT; ogni altro valore, `''` incluso, → errore.
- D6 — (a): `None` nella collezione legato come NULL, semantica SQL a tre valori; da documentare nella guida query.
- D7 — (a): `set` e `frozenset` accettati come collezioni.
- D8 — (b): `exclude_logical_deleted='mark'` con aggregati, DISTINCT o GROUP BY solleva un errore esplicito.

Aggiunte dal quality check della Macro 1, decise il 2026-10-01:

- D9: `:env_x` con la chiave assente dall'ambiente solleva `Missing query parameter`
  (comportamento attuale, `src/asqueel/compiler.py:156`). Il legacy lega NULL
  (`execute.py:93`); la differenza è voluta.
- D10: DISTINCT con `order_by` su un'espressione assente dalla proiezione (R18)
  solleva un errore di Asqueel su entrambi i backend, prima dell'esecuzione.
