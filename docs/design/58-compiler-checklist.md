# 58 — Checklist del compilatore e stato corrente

Aggiornato il **16 ottobre 2026**, sul branch `codex/core-single-read-path`.
Base operativa della consegna: **`e96f0c14c27ab3366b7240de67c713b5712c4a50`**.
Questa fotografia sostituisce le precedenti liste cumulative: i rapporti delle
singole fasi conservano lo storico, non sono TODO concorrenti.

Il passaggio definitivo al percorso unico delle letture è completato e verificato
nel perimetro concordato. Non equivale al porting integrale di GenroPy.
Nessuna scrittura viene implementata o certificata da questa checklist.

- 🟢 Implementato e verificato nel perimetro indicato.
- 🟡 Verifica, integrazione o contratto ancora da completare.
- 🔴 Funzionalità non disponibile; non significa automaticamente blocco della fusione.
- I rinvii espliciti sono separati dalle lacune ancora da valutare. Questo
  censimento non autorizza nuove sintassi, implementazioni o cambi di comportamento.

## 1. 🟢 Percorso unico e modello

- [x] AsqueelDb, build_database, CLI e hosting usano il DbModel gerarchico.
- [x] Il renderer usa walk generica e finalize; espande prima le options su una
  copia privata della source e non ripete gli effetti durante il resto della visita.
- [x] `objects_tree` restituisce il modello; `objects` collega lo stesso modello
  al database operativo. Non ci sono due costruzioni parallele.
- [x] `SqlTable.model` è il DbTableObj dell'albero; colonne fisiche in `columns`,
  virtuali in `virtual_columns`, compositi separati, attributi sui nodi.
- [x] Il ramo `relations` è l'autorità per la navigazione; le inverse restano
  registrate anche quando la loro compilazione verso molti non è supportata.
- [x] Eliminati vecchio compilatore/scanner, QueryPlan/Fragment, SqlStatement
  e wrapper duplicati SqlColumn/SqlRelation. Nessun fallback o shim provvisorio.
- [x] I DTO di catalogo rimasti servono a introspezione/codec/proiezione;
  non sono un secondo modello operativo accettato dal compilatore.
- [x] Options condivise compongono tipo, attributi e relazioni senza duplicati,
  incluso `invc.product_group._row_count`.
- [x] Le 12 differenze residue nell'ordine delle colonne rispetto al legacy sono
  accettate. Non sono correzioni pendenti e non richiedono ordinamenti nel compilatore.

Fonti: [93](93-options-first-object-renderer.md),
[94](94-shared-option-fields.md), [98](98-single-read-path.md).

## 2. 🟢 Compilazione, parametri e SELECT

- [x] Unico QueryCompiler; contenitore di clausole SqlCompiledQuery sul modello
  legacy, assemblaggio/preparazione delegati agli adapter.
- [x] CompiledQuery contiene SQL e kwargs separati. `query.compiled` non esegue
  SQL né apre connessioni. `driver.prepare_sql(sql, kwargs, snapshot)` prepara
  il contenitore eseguibile; `db.execute(compiled)` è il punto di esecuzione.
- [x] Riferimenti `$campo` e `@relazione.campo`, espressioni SQL fidate, AS e
  alias automatici secondo gli algoritmi legacy. Non esiste la sintassi aggiunta
  `$"nome quotato"`; non si promettono protezioni da scanner su commenti/literal.
- [x] Parametri espliciti, ambiente e locali delle formule; scope delle sottoquery
  isolati. Alias di tabella e mangler dei parametri sono distinti.
- [x] Binding mancanti portati a NULL come deciso; preparazione degli adapter
  verificata, inclusa la regressione `:ids` / `:ids2` con confine di parola.
- [x] `embedFieldPars` nel WHERE secondo il legacy: un valore simbolico `$campo`
  o `@relazione.campo` riconosciuto può diventare un riferimento SQL.
  Non è un canale per accettare indiscriminatamente valori esterni non fidati.
- [x] WHERE, ORDER BY, LIMIT/OFFSET, DISTINCT, GROUP BY/HAVING; ordine di tabella
  quando applicabile e trattamento legacy di `group_by='*'`.
- [x] Pkey automatica controllata da `addPkeyColumn`, False per default:
  la decisione è già acquisita, non è più una firma aperta.
- [x] `*` e colonne esplicite; fisiche e virtuali statiche secondo il modello.
  bagFields regola le X, salvo la regola legacy `bagFields or for_update`.
- [x] Count: COUNT(*) nelle query ordinarie, chiavi del raggruppamento per GROUP BY,
  proiezione conservata per DISTINCT; rimozione dell'ordinamento.
- [x] FOR UPDATE nel profilo concordato; nessun lock durante la sola compilazione.
- [x] ILIKE adattato su SQLite con sostituzione limitata all'operatore.

Fonti: [86](86-legacy-compiler-logical-phases.md),
[88](88-legacy-rewrite-phase2.md), [90](90-legacy-rewrite-phase4.md),
[91](91-legacy-tree-count.md), [98](98-single-read-path.md).

## 3. 🟢 Relazioni, formule, options e macro nel perimetro supportato

- [x] Relazioni verso uno anche concatenate, riuso delle JOIN per percorso e
  relazioni distinte verso la stessa tabella; chiavi fisiche composte.
- [x] Chiavi sorgente da formula, compresi `last_invoice_id` e `first_product_id`.
  Le inverse ordinarie dichiarate one_one sono distinte dalle relazioni verso molti.
- [x] Condizioni ON già nei joiner: confronto legacy e test su root e percorso
  padre. Questo non certifica tutta la grammatica nativa di virtualRelation.
- [x] Formula SQL, dipendenze, aliasColumn su percorsi supportati, cicli e `var_*`.
- [x] `select`, `exists`, `select_*`, correlazioni `#THIS`, sottoquery nominate e
  relativi binding. `#THIS` è espanso prima della raccolta dei riferimenti.
- [x] Metodi `sql_formula_<nome>(attr)` e riferimenti stringa `subquery_*` sulla
  tabella corrente; non equivalgono a un RuntimeModel completo.
- [x] subQueryColumn da mapping; modi scalare/JSON/XML nel profilo del dialetto.
  Riferimenti stringa per scalare/JSON, con il limite XML legacy indicato sotto.
- [x] bagItemColumn su PostgreSQL: XPath, attributi/posizioni, cast e binding.
- [x] Draft, cancellazione logica e partition nativa con solo valore corrente
  scalare; required e bypass come concordato. Verificati i filtri sui 74 modelli.
- [x] Default delle sottoquery e mancata propagazione dei filtri root nelle JOIN
  secondo il legacy. Altre options conservate senza inventare effetti SQL.
- [x] Macro IN_RANGE, PERIOD, THIS e riferimenti `#nome` a `select_nome`.
  IN_RANGE usa la correzione approvata per gli estremi NULL su PostgreSQL.

Fonti: [89](89-legacy-rewrite-phase3.md), [90](90-legacy-rewrite-phase4.md),
[capitolo macro](64-compiler-macros.md). I conteggi del vecchio compilatore
(460/462 formule, inverse child_count incluse) non certificano il percorso attuale:
le compilazioni che attraversano molti sono ora escluse per decisione esplicita.

## 4. 🟢 Terminali delle letture e lock

- [x] `fetch()` restituisce NamedList di Toolbox: nome/posizione, righe modificabili,
  stessa API sui due dialetti; ogni fetch riesegue la query.
- [x] `count()` esegue e interpreta il risultato secondo il legacy.
- [x] `record()` è lazy, conserva il risultato fino a refresh, gestisce
  ignoreMissing e segnala più righe; output `dict` e `record` disponibili.
- [x] Il record legge le colonne fisiche, X incluse per default, senza aggiungere
  virtuali statiche o filtri impliciti query. Output record è una Bag senza
  resolver di relazione; le colonne X sono convertite in Bag.
- [x] Query con lock include X nell'espansione di `*`, anche con bagFields=False;
  una proiezione esplicita resta esplicita. `*` include anche virtuali statiche:
  per sole fisiche costruire la proiezione da `table.model.columns`.
- [x] PostgreSQL FOR UPDATE OF t0. SQLite BEGIN IMMEDIATE senza transazione aperta;
  se già aperta, acquisizione con UPDATE senza righe sulla tabella fisica.
  È un raccordo runtime concordato, non un algoritmo attribuito al legacy SQLite.
- [x] Verificate contesa su seconda connessione, rilascio al rollback, stessa
  connessione/transazione e assenza di commit impliciti o modifiche alle righe.

Fonti: [92](92-hierarchical-fetch-count.md),
[97](97-read-write-contracts.md), [98](98-single-read-path.md).

## 5. Mancanze funzionali e contratti non ancora coperti

Queste voci descrivono il porting incompleto, non requisiti aggiunti alla fusione.
Non confondere «non implementato» con «rinviato dall'utente».

| Stato | Funzionalità | Cosa manca esattamente |
| --- | --- | --- |
| 🔴 | virtualRelation nativa | Le dichiarazioni sono conservate, ma il compilatore attraversa i joiner delle relation/weak_relation sulle colonne. Manca il raccordo SQL di virtualRelation: abbreviazione di percorso, destinazione esplicita, condizione, var_*, ask e derivazioni ammesse. Non va presentata come già compilabile neppure la sola abbreviazione `customer` di invoice_row. |
| 🟡 | Copertura dei join dichiarativi | Esistono joiner e condizioni ON legacy testate; manca una certificazione completa delle forme native e delle condizioni ulteriori. Il vecchio punto generico «joinColumn da portare» non autorizza una nuova firma: la grammatica 42 distingue relation/weak_relation e virtualRelation. |
| 🔴 | Macro non portate | `#ENV`, TSQUERY, TSRANK, TSHEADLINE, VECQUERY, VECRANK, BAG e BAGCOLS. Serve ancora il confronto conclusivo del contratto; `:env_nome`, SQL esplicito e bagItemColumn non ne sono sostituti equivalenti. |
| 🔴 | Selection e risultati legacy estesi | `query.selection()` è esplicitamente non supportata. Mancano il contenitore Selection e i suoi output; record supporta solo dict/record, senza resolver lazy/eager per navigare le relazioni e senza gli altri output legacy. |
| 🟡 | RuntimeModel e composizione dei mixin | Il collegamento a SqlTable, x_table_class e metodi formula esiste. Non è ancora definita/certificata l'integrazione completa del RuntimeModel o una nuova composizione di classi/mixin. Resta lavoro separato. |
| 🟡 | Composite come valore di proiezione | Chiavi e vincoli composti esistono; manca un contratto per proiettare compositeColumn come singolo valore. Non introdurre concatenazioni o conversioni implicite. |
| 🟡 | Altre opzioni SQL legacy | DISTINCT ON, tuple IN, convenzioni REGEXP e opzioni ulteriori di lock non hanno una copertura strutturata certificata. SQL esplicito eventualmente accettato non equivale a un contratto completo. |
| 🟡 | Partition oltre il valore corrente | Gli insiemi di valori ammessi non sono acquisiti per l'option nativa. Il contratto approvato resta solo scalare; nessuna chiave di ambiente aggiunta per deduzione. |
| 🟡 | Opzioni avanzate delle sottoquery | Il profilo accetta le clausole portate; rifiuta opzioni estranee e valori diversi da subtable='*', addPkeyColumn=False, ignoreTableOrderBy=True. Il supporto più ampio del legacy non è certificato. |

### Opzioni dell'API query non portate

Il rifiuto esplicito in `application_table.py` riguarda anche:

- `relationDict`, `joinConditions`, `sqlContextName`: nessun override per-query
  del ramo relazioni/contesto SQL legacy. Le condizioni nei joiner del modello
  già testate sono un contratto diverso.
- `ignoreTableOrderBy` e `subtable` nella query applicativa: nessuna API generale
  per quei comportamenti; i valori ammessi nelle sottoquery sono indicati sopra.
- `_storename`/`storename`, `locale`, `checkPermissions`: nessuna selezione per-query
  dello store, del locale o verifica dei permessi tramite queste opzioni legacy.
  L'ambiente del database esistente resta distinto.
- `aliasPrefix`, `mode`, `lazy`, `eager`, `virtual_columns`: nessuna configurazione
  pubblica di quel tipo per alias, output, risoluzione o proiezioni aggiuntive.
- `ignoreMissing` e `ignoreDuplicate` sulla query: non disponibili. `ignoreMissing`
  è invece acquisito su record; record continua a segnalare più righe.
- `aggregateRows`/`_aggregateRows`: esclusi con il meccanismo delle righe esplose.

Questi sono limiti dell'API attuale, non una proposta di ripristinare tutti i
parametri. `addPkeyColumn` non appartiene più a questo elenco: è supportato.

### Limiti concreti dei dialetti e del riferimento

- 🔴 SQLite non implementa bagItemColumn XPath né gli aggregati JSON/XML delle
  subQueryColumn. Il rifiuto è esplicito; non si aggiunge un fallback Python.
- 🟡 EXISTS SQLite: è conservato il limite legacy delle doppie parentesi nei
  casi documentati. Il test che attende l'errore SQL non certifica l'esecuzione
  positiva di quella forma. Non riaprire automaticamente la decisione.
- 🟡 XML da metodo subquery referenziato per stringa non è supportato: il legacy
  richiede le colonne nel mapping alla dichiarazione. Nessuna scelta automatica
  di colonne, prima riga o aggregati è stata aggiunta.

### Rinvii espliciti, non blocchi della fusione

- 🔴 Relazioni verso molti: nessuna JOIN che esploda righe, DISTINCT implicito
  o ricomposizione runtime. Il pattern `@relazione.operazione(...)` è riconosciuto
  e cerca `many_*` via getattr; nessun handler esiste. Sum/calculate/first/last,
  aggregazione JSON/XML e LATERAL restano da definire ([R-10](41-deferred-features.md#r-10--compilazione-delle-relazioni-verso-molti-sul-nuovo-albero)).
- 🔴 pyColumn: dichiarazione conservata, calcolo Python dei risultati non portato.
  Di conseguenza `*` non è utilizzabile su adm.htmltemplate_atc con la pyColumn
  statica presente; non la si salta silenziosamente.
- 🔴 Query concatenate SELECT FROM SELECT e operatori UNION/UNION ALL/INTERSECT/EXCEPT,
  con relativi alias, relazioni esterne e binding ([R-09](41-deferred-features.md#r-09--query-concatenate-e-operatori-fra-query)).
- 🔴 `#PREF`: nessun recupero automatico del default o sistema sostitutivo di preferenze
  ([R-08](41-deferred-features.md#r-08--macro-pref)).
- 🔴 Wildcard avanzati per prefisso/percorso: restano solo `*` e colonne esplicite
  ([R-11](41-deferred-features.md#r-11--wildcard-avanzati)).
- 🔴 Nuova grammatica query/wherebag, nuove sintassi variant, serializzazione dedicata
  e controllo SQLGlot opzionale per fonti insicure: non integrati nel core.
  Le query attuali accettano SQL fidato, non costituiscono una sandbox per il browser.
- 🔴 Sulle virtualRelation restano esclusi inverse automatiche, limit, order_by e
  one_one; aliasTable resta esclusa. Non sono prerequisiti impliciti del raccordo.

I rinvii strutturali toolColumn, system_records, release e diagnostics restano
nel [registro 41](41-deferred-features.md); non sono lavoro del compilatore letture.
`sys_fields(syscode=True)` è invece già disponibile. Nessuna voce DML è inclusa.

## 6. Verifiche e lavoro prima/durante la fusione

- [x] **4.253 test passati, 12 skip, 16 deselected**, in 210,70 secondi:
  `PYTHONPATH=src python -m pytest @tests/read_path/pytest.args --no-cov -q --tb=short`.
  I deselected sono casi del writer in file misti; 27 file dipendenti dalle scritture
  sono esclusi esplicitamente dal manifest, non saltati globalmente.
- [x] PostgreSQL e SQLite reali, test record/lock e NamedList, CLI e hosting.
- [x] 74 modelli: struttura, attributi, relazioni e JSON migration confrontati
  con artefatti indipendenti; applicazione/introspezione/rediff su PostgreSQL.
- [x] Ruff, mypy (57 file), Sphinx con warning come errori; wheel installata
  separatamente dal checkout e migration 0.2.2 da PyPI.
- [x] Checklist riallineata al percorso unico; consegna al writer preparata nel
  [documento 99](99-writer-handoff-single-read-path.md).
- [ ] 🟡 Consolidare una matrice completa dei risultati sui dati delle formule
  native supportate, distinguendo errori, ambiente mancante e rinvii. I test
  mirati e il confronto dei 74 modelli non sono una verifica di ogni formula
  su dati reali; i vecchi conteggi di sola compilazione non la sostituiscono.
- [ ] 🟡 Sul branch fuso verificare i contratti condivisi di modello, proiezione,
  contenitore eseguibile, record e connessione/transazione/lock del documento 97.
- [ ] 🟡 Eseguire la suite intera senza le esclusioni riservate al writer, poi CI.
  Nessuna CI integrata, fusione, pubblicazione o push è certificata da questa consegna.

**Non ci sono blocchi funzionali noti nei contratti delle letture consegnati al
writer.** Le lacune sopra elencate restano visibili: non sono chiuse dal numero
complessivo dei test e non diventano automaticamente lavoro da fare prima della fusione.

Evidenze: [rapporto 98](98-single-read-path.md),
[verifica riproducibile](evidence/single-read-path/verification.json),
[contratti 97](97-read-write-contracts.md).
Storico algoritmi/decisioni: [piano 86](86-legacy-compiler-logical-phases.md),
[grammatica 42](42-configuration-grammar.md), [indagine 55](55-select-sql-and-kwargs-investigation.md),
[piano 56](56-read-compiler-plan.md), [confronto branch 57](57-legacy-compiler-refactoring-review.md).
