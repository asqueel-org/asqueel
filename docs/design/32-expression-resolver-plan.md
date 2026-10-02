# 32 — Piano: parser delle espressioni asqueel, resolver unico, relazioni e macro

Stato: proposta, da approvare. Nessun passo è avviato.
Baseline: `04bef4c`, versione 0.4.0 pubblicata; 845 test, copertura 95%.
Riferimento legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, più i commit di
`origin/develop` che toccano `gnrsqldata/` e `gnrsqlmodel/` dopo quel commit
(D7).

## Obiettivo e collocazione

Un solo componente interpreta le espressioni asqueel e un solo componente ne
risolve i riferimenti. Lo usano compiler, modello, policy e `SqlTable.column()`.
È il nucleo di F2 del [piano 15](15-operational-plan.md) (LT04, LT03 attraverso
i path, LT05 per direzione e cardinalità) ed è il prerequisito di GEP 1 e delle
`virtualRelation`.

Lo scopo non è un compiler che funzioni: è il compiler migliore possibile,
costruito sull'evoluzione del legacy e sui suoi difetti documentati.

## Vincolo di compatibilità con GenroPy

Un'espressione scritta per GenroPy deve avere lo stesso significato in asqueel,
quando asqueel la supporta. Una forma non supportata produce un errore esplicito,
mai un risultato diverso.

La sintassi legacy è quella a cui gli sviluppatori sono abituati. Cambiarla
richiede motivazioni davvero forti, scritte nella decisione che la cambia.
Asqueel non aggiunge grafie alternative a quelle legacy (decisione del
2026-10-01, D2 e D4).

- Sintassi conservata: `$col`, `@fk.col`, `@rel.@rel2.col`, `:param`, `:env_x`,
  `#THIS.<path>`, `#NOME(argomenti)`, `#nome` per le sottoquery nominate.
- Nomi delle relazioni come nel legacy: `@<colonna fk>` per la relazione
  uscente, `@<relation_name>` per l'inversa (`gnrsqlmodel/model.py` `addRelation`).
- Nomi dell'API come nel legacy: `column()`, `originalColumn`, `relatedTable()`,
  `relatedColumn()`, `relation_path`.
- Ogni divergenza intenzionale viene registrata in
  [adattamenti legacy](../adattamenti-legacy.md) con il caso che la mostra.

Il compiler legacy non è il modello da copiare. Le forme che il legacy stesso
sta rimuovendo non vengono implementate (sezione «Fuori da questo incremento»).

## Regole di esecuzione

Per ogni passo: sorgente legacy → caso eseguibile → test di regressione nuovo
fallente → implementazione → confronto PostgreSQL/SQLite → aggiornamento delle
sole pagine interessate. Come nel piano 30.

- Le espressioni vengono analizzate una volta. Nessuna passata regex sul testo
  SQL dopo l'analisi.
- Il modello risolto è immutabile. La compilazione non scrive nei metadati
  condivisi (il legacy lo fa: `compiler.py:608`, `:626`).
- Un nome mancante produce sempre un errore tipizzato. Mai `None`.
- Nessun cambiamento allo SQL prodotto oggi, salvo le differenze dichiarate
  nelle decisioni D1–D4. Il passo 7 lo verifica su tutto il corpus.

## Fonti legacy usate

- Compiler: `gnrsqldata/compiler.py` su `origin/develop` (`compiler_next.py` è
  una copia identica); README di `gnrsqldata`, `gnrsqlmodel`, `gnrsqltable` con
  i marker REVIEW; codice morto annotato nella PR #647.
- Relazioni: `gnrsqlmodel/model.py` `addRelation`, `resolvers.py`
  `RelationTreeResolver`, `table.py` `column`/`_relatedColumn`/`fullRelationPath`/
  `resolveRelationPath`/`getTableJoinerPath`; issue #548 e PR #578 (cache e lock);
  PR #1353 (RuntimeModel come strato sopra il modello statico).
- Macro: PR #650 e #660 (registry su `develop`, non letto dal compiler); PR #1352
  (registry con contesti nominati, `gnrsqlmacros.py`, matrice macro × posizione);
  issue #617, #618, #541, #624.
- Subquery: serie `sql_review/subquery_refactor_v2`…`v4`, PR #544 e #494; forma
  canonica `join_to`/`join_from`/`join_condition` di `subquery_utils.py` (v4).
- Proposte: GEP 1 e GEP 2 in `genropy_meta` (stato Discussion); discussione
  `virtualRelation` in genropy/genropy_meta#1; issue #616–#625.

Difetti del legacy da non riprodurre, con la fonte:

- quattro modi di percorrere un path, che non concordano (compiler,
  `column()`, `fullRelationPath`, `resolveRelationPath`);
- `column()` restituisce `None` per un nome semplice mancante e alza
  un'eccezione per un path mancante;
- la chiave dei join usa `many_relation` senza package (`compiler.py:540`): una
  FK verso la stessa tabella e la sua inversa danno la stessa chiave;
- l'ordine fra macro e path: `#THIS.@rel.col` dentro una formula non funziona
  (`updateFieldDict` riscrive prima `@rel.col`); `TSRANK` viene espanso dopo
  `templateReplace` e lascia path non risolti;
- una macro assente nel dialetto resta come testo nello SQL (`#TSQUERY` su
  SQLite);
- `#ENV` e `#PREF` inseriscono valori nel testo SQL senza escape;
- la cardinalità è distribuita fra `mode`, `one_one` e `joinConditions`.

## Passo 1 — Corpus di compatibilità

- Raccogliere le espressioni dai test legacy: `tests/sql/test_compiler_coverage.py`,
  il corpus di `tests/sql/test_compiler_factory.py` su `test_invoice`,
  `tests/sql/test_model_structure.py` per `column()` e relazioni.
- Per ogni espressione registrare cosa produce il legacy: tabelle attraversate,
  join, colonna finale, nome del risultato, eccezione.
- Classificare ogni caso: supportato in questo incremento, rinviato con
  errore esplicito, divergenza intenzionale.
- Rieseguire i casi nel legacy in fixture isolate, come nel passo 1 del piano 30.

**Uscita:** matrice nello stile del documento 31, con fonte legacy per ogni riga
e decisioni D1–D8 chiuse prima del passo 2.

## Passo 2 — Contratto delle relazioni

- `Relation` (`contracts.py`) registra la direzione (uscente, inversa) e la
  cardinalità (molti-a-uno, uno-a-molti, uno-a-uno), al posto di `mode` e
  `one_one` separati.
- Ogni relazione è dichiarata una volta. Il modello risolto ne ricava le due
  direzioni.
- Nome dell'uscente: `@<colonna fk>`. Nome dell'inversa: `relation_name`; senza
  nome, la regola legacy `<schema>_<tabella>_<colonna>` con il flag private.
  Collisioni di nome → errore in risoluzione del modello.
- La relazione registra se la FK ammette NULL. Il compiler potrà scegliere fra
  INNER e LEFT JOIN; in questo incremento resta LEFT JOIN.
- Le relazioni composite conservano le coppie di colonne attuali.

- Il contratto deve accogliere `virtualRelation` come un altro tipo della stessa
  relazione, senza una struttura separata: origine (FK, logica, derivata), sola
  lettura, condizione, ordine. Il resolver e le funzioni del GEP 1 lavorano su
  tutti i tipi allo stesso modo (vincolo del 2026-10-02).

**Uscita:** inverse visibili nel modello e in `SqlTable.relations`; test su
FK verso la stessa tabella, due FK verso la stessa tabella, relazioni composite.

## Passo 3 — Parser delle espressioni asqueel

- Il parser usa il livello lessicale esistente (`dialects/postgres.py` `_tokens`)
  per stringhe, identificatori quotati e commenti.
- Produce nodi tipizzati: colonna `$x`; path `@a.@b.c` con i segmenti; parametro
  `:p`; `#THIS.<path>`; chiamata `#NOME(argomenti)` con argomenti analizzati
  ricorsivamente; funzione su relazione `@rel.f(argomenti)`; riferimento a
  sottoquery `#nome`; testo SQL.
- Ogni segmento di relazione richiede la `@`, come nel legacy
  (`@customer_id.@country_id.name`). Un segmento intermedio senza `@` produce un
  errore di sintassi (D4). Una table alias legacy si scrive anch'essa con la `@`
  (`@customer.account_name`, `test_compiler_coverage.py:2729`).
- La funzione su relazione (`@rel.f(argomenti)`) viene letta come nodo, così il
  GEP 1 aggiunge solo le funzioni. Finché non esistono funzioni, la
  compilazione fallisce come per qualsiasi nome sconosciuto: nessun messaggio
  provvisorio.
- Gli errori di sintassi riportano la posizione nell'espressione.

**Uscita:** parser con test sul corpus del passo 1, comprese le forme rifiutate.

## Passo 4 — Resolver unico

- Ingresso: un nodo, la tabella di partenza, il contesto (alias corrente,
  tabella esterna per `#THIS`).
- Uscita: colonna finale con i suoi metadati; passaggi attraversati, ognuno con
  relazione, direzione e cardinalità; espansione degli `aliasColumn`
  (`relation_path`).
- La chiave di un join è la catena canonica dei passaggi, schema incluso.
- Un passaggio uno-a-molti produce un errore: è un controllo di correttezza
  (nessun join che moltiplica le righe), non un segnaposto per il GEP 1.
- Errori tipizzati con i nomi del legacy (D8): relazione mancante, colonna
  mancante, path non valido.
- Sostituisce i walker attuali: `compiler._Context.field` e `related`,
  `model._resolve_aliases`, `model._physical_policy_column` e
  `compiler._Context.policy_field`.

**Uscita:** un solo walker nel codice; test sulle forme del passo 1 e sui casi
di alias attraverso relazioni.

## Passo 5 — Superficie applicativa

- `SqlTable.column()` accetta `name`, `$name` e path `@`; restituisce la colonna
  finale del resolver.
- `SqlColumn.relatedTable()` e `relatedColumn()` come nel legacy
  (`gnrsqlmodel/columns.py:170-191`).
- I metadati (dtype, ui, readonly) letti attraverso path e alias vengono da una
  fonte sola. Oggi le fonti sono due: `model.py:224-241` e
  `application_table.py:78`.
- `ResultColumn.source` di un alias proiettato indica la colonna di destinazione.

**Uscita:** casi di `test_model_structure.py` (LT03, LT04) eseguiti contro
asqueel, con le divergenze registrate.

## Passo 6 — Registry delle macro

- Registrazione per livello: core, dialetto, applicazione, package. Un nome
  duplicato → errore, salvo `replace=True` (come #650).
- Contesti nominati e validati in registrazione: columns, where, order_by,
  group_by, having, condizione di relazione, formula, record. Il legacy non
  espande le macro in group_by, having e nei record.
- La callback riceve un contesto con alias corrente, tabella, compiler e
  parametri. #1352 non lo prevede, e per questo lascia `#THIS`, `#PREF` e `#ENV`
  come casi speciali.
- L'espansione produce nodi, che il resolver risolve. Una macro non registrata
  per il dialetto → errore di compilazione.
- Macro implementate in questo incremento (D5): `#THIS` portato sul parser;
  `#IN_RANGE` e `#PERIOD` con la semantica legacy.

**Uscita:** matrice macro × contesto × dialetto, come il test
`test_macro_contexts.py` di #1352.

## Passo 6b — Espansione delle colonne (LT09)

- Le espansioni delle colonne seguono il legacy nello stesso identico modo,
  salvo divergenze motivate su basi esterne. Tabella
  delle decisioni in [adattamenti legacy](../adattamenti-legacy.md), sezione
  «Espansione delle colonne nella SELECT».
- Decise il 2026-10-01: `*` identico al legacy; nomi automatici `colToAs`
  identici al legacy (D1); `*prefix_`, `*nome`, `*@rel`, `*@rel.prefix_` e
  `*@rel.(a,b)` non supportati (motivi nella tabella; per `*prefix_`
  genropy/genropy#1504, per le forme su relazione #623 e GEP 1 §9.6).
- Da decidere: modalità count, colonna `pkey` aggiunta.
- Il modello registra l'attributo `static` delle colonne virtuali e il `dtype`
  `X`; le query accettano `bagFields`.

**Uscita:** test per ogni forma, confrontati con il legacy sul corpus del passo 1.

## Passo 7 — Compiler sul nuovo parser

- Il compiler e il modello usano solo parser e resolver. Spariscono le regex
  `_FIELD`, `_PATH`, `_THIS`, `_MACRO` (`compiler.py:24-27`) e
  `_RELATION_FIELD` (`model.py:277`).
- Prima del passo: salvare lo SQL e i parametri di tutte le query compilate
  dalla suite. Dopo il passo: stesso SQL, salvo le differenze di D1–D4.
- Benchmark `docs/design/evidence/query_benchmark.py` prima e dopo. Il tokenizer
  oggi viene eseguito più volte per ogni WHERE (issue #3).

**Uscita:** suite completa verde, confronto dello SQL salvato, benchmark.

## Passo 8 — Accettazione e documentazione

- Guide: `queries.md:64-65` e `:74`, `models.md:165-166` oggi contraddicono il
  codice; `compiler.md`, `limitations.md`, release notes.
- [Adattamenti legacy](../adattamenti-legacy.md): ogni divergenza del passo 1.
- Piano 15: stato di F2; residui di F3 rivisti (sezione seguente).
- `roadmap/07_legacy_compiler_experiments.md`: correggere i nomi dei branch
  (`sql_review/…`, non `feature/…`) e l'affermazione sullo switch di
  `record.py`, che non esiste.

**Uscita:** build Sphinx rigorosa, ruff, mypy e suite verdi.

## Fuori da questo incremento

- Passaggi uno-a-molti: vengono con GEP 1 (funzioni sulle relazioni compilate
  come subquery correlate). Non si implementano join che moltiplicano le righe
  né la ricomposizione Python (`_aggregateRows`, issue #1354).
- `joinConditions`: non si implementa. GEP 2 e la discussione `virtualRelation`
  lo rendono deprecato (#625).
- `*nome` e `*@rel.(a,b)`: non si implementano (GEP 1 §3 e §9.6).
- Table alias (LT06), `getTableJoinerPath`: incremento successivo.
- `virtualRelation`: dopo la chiusura della discussione genropy/genropy_meta#1.
- Macro `#BAG`, `#BAGCOLS`, `TSQUERY`/`VECQUERY`, `#PREF` (livello applicazione).
  `#ENV` non si porta: lo sostituiscono i parametri `:env_*` (#618).
- Composizione package/mixin (LT01), roundtrip delle migrazioni (LT37).

Conseguenza sul piano 15: i residui di F3 «relationDict, joinConditions,
to-many» diventano «GEP 1 sulle relazioni inverse; `virtualRelation`».

## Decisioni aperte

- **D1 — Nome automatico di `@rel.col` — DECISA (2026-10-01).** Regola legacy
  `colToAs`: `_customer_id_name`. Client e server del framework ricalcolano il
  nome con la stessa regola (`genro_grid.js:1370`, `:1861`, `apphandler/export.py:283`).
  È un breaking change per asqueel 0.4, che produce `customer_name` (R33).
- **D2 — `x_name` — DECISA (2026-10-01).** `x_name` come nome di navigazione è
  un'estensione di asqueel: nel legacy la relazione uscente si chiama sempre
  `@<colonna fk>`. Si rimuove. I nomi legacy restano: `relation_name` per
  l'inversa, `one_name` e `many_name` come etichette. È un breaking change per
  asqueel 0.4. Usi da aggiornare: `model.py:99` e `:140`, `projection.py:152`
  (identità della relazione nella proiezione verso le migrazioni), la guida
  (`models.md:31`, `:119`, `formulas.md:40`, `troubleshooting.md:30`), il
  tutorial `docs/guide/_examples/shop_tutorial.py` e i test che dichiarano
  `x_name`.
- **D3 — Nome mancante in `column()` — DECISA (2026-10-02).** Identico al
  legacy (`gnrsqlmodel/table.py:514-565`): un nome semplice mancante restituisce
  `None`; un path con una relazione mancante alza l'eccezione. Il `None` è
  l'idioma del framework per sapere se una tabella ha una colonna (28 righe in
  `gnrpy` e `resources`, per esempio `gnrdbo.py:187`, `:1144`).
- **D4 — Segmenti intermedi senza `@` — DECISA (2026-10-01).** La forma
  `@customer.country.name` è un'estensione di asqueel che il legacy non accetta
  (`compiler.py` `_getRelationAlias`: un nodo colonna senza `joiner` alza
  `KeyError`). Si rimuove: ogni segmento di relazione richiede la `@`. È un
  breaking change per asqueel 0.4. Da aggiornare: `docs/guide/queries.md:172`,
  `docs/guide/models.md:152`, test
  `test_legacy_and_native_paths_have_same_sql_and_default_alias`
  (`tests/native_compiler/test_aliases.py:56`).
- **D5 — Macro del primo incremento.** Proposta: `#THIS`, `#IN_RANGE`,
  `#PERIOD`, una per volta.
  - `#THIS` — DECISA (2026-10-02): stessa semantica del legacy: colonna o path
    della riga esterna, risolto dal resolver della query esterna, con i join
    nella query esterna. Vale anche nelle `sql_formula`, dove il legacy non
    espande `#THIS.@rel.col` (genropy/genropy#1505). Fuori da un contesto
    correlato: errore.
  - `#IN_RANGE(valore, inizio, fine)` — DECISA (2026-10-02): semantica del
    legacy (`compiler.py:1316-1346`), estremi inclusi, `NULL` come estremo
    aperto, entrambi `NULL` vero. Argomenti: qualunque espressione del parser.
    Espansa in tutti i contesti, compresi `group_by`, `having` e record. Solo il
    nome `#IN_RANGE` (il legacy `#BETWEEN` è stato rinominato in #644).
  - `#PERIOD($campo, :p)` — nelle prime macro (2026-10-02). La decodifica del
    periodo è delegata a `genro_toolbox.dates.parse_period(text, workdate,
    locale)` (genro-toolbox 0.15.0, commit `c7a26f9`), con `workdate` e
    `locale` del contesto: restituisce `DatePeriod(start, end)`, `None` per un
    estremo aperto; un valore non riconosciuto alza `PeriodError`. Dipendenza
    `genro-toolbox>=0.15.0` aggiunta da questo passo. Divergenze dal
    `decodeDatePeriod` legacy: 432 casi su 2796, motivate in
    `tests/data/period_parser_divergences.json` di genro-toolbox. SQL (deciso
    2026-10-02): sempre chiuso a sinistra e aperto a destra, `campo >= :p_from
    AND campo < :p_to_next` con `p_to_next` il giorno dopo la data finale; un
    giorno solo usa la stessa forma; solo inizio `>=`; solo fine `<`; nessun
    estremo `true`. Su `date` il risultato è quello del legacy; su timestamp
    include l'ultimo giorno (difetto del `BETWEEN` legacy, REVIEW in
    `compiler.py:1388-1390`; caso reale `erpylight th_pt_distinta.py:126-129`).
    Secondo argomento (deciso 2026-10-02, da rivedere dopo
    genropy/genropy#1509): `:p` per un parametro, obbligatorio; un valore
    letterale si scrive tra apici, `#PERIOD($date, '2024')`,
    `#PERIOD($date, 'today;today+7')`; un parametro mancante è sempre un
    errore. Nessun ripiego da nome a letterale come proposto in
    genropy/genropy#541: un parametro scritto male diventerebbe un periodo senza
    avviso, e `\w+` non ammette valori come `'today;today+7'`. Il periodo non può
    venire da una colonna (`#PERIOD($date, $col)`): la decodifica avviene in
    Python durante la compilazione; il legacy non espande quella forma. Per due
    date della riga si usa `#IN_RANGE`.
- **D6 — Inverse e cardinalità.** Proposta: dentro questo incremento (passo 2).
- **D7 — Riferimento legacy.** Proposta: `fa35e5a` più i commit successivi di
  `develop` su compiler e modello, elencati nel passo 1.
- **D8 — Eccezioni — DECISA (2026-10-02).** Gerarchia coerente con una base
  sola, `GnrSqlException` (nome legacy). Ne derivano, un caso per classe:
  `GnrSqlMissingTable` (tabella mancante), `GnrSqlMissingField` (relazione
  mancante), `GnrSqlMissingColumn` (colonna finale mancante in un path),
  `GnrSqlInvalidVirtualColumn` (virtuale non valida), `GnrSqlRelationError`
  (dichiarazione delle relazioni). Nel legacy queste derivano da `GnrException`
  e sfuggono a `except GnrSqlException` (`gnrsql_exceptions.py:95-108`). Gli
  altri errori di asqueel entrano nella gerarchia con i nomi legacy in un lavoro
  a parte. Nessun vincolo di compatibilità con i `ValueError` attuali.
- **D9 — Colonna `pkey` automatica — DECISA (2026-10-02).** Il nucleo di asqueel
  non la aggiunge. Il legacy aggiunge `$<pkey> AS pkey` di default
  (`addPkeyColumn=True`, `query.py:150`, `compiler.py:947-949`), salvo tabella
  senza pkey, count, `distinct`, `group_by` e subquery delle formule (`:418`);
  con `SUM`/`COUNT` senza `group_by` la aggiunge comunque perché l'aggregato è
  riconosciuto dopo (`:1008-1009`). Il comportamento va nel futuro adattatore
  legacy, registrato in `docs/adattamenti-legacy.md`.
