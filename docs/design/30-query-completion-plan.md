# 30 — Piano: completamento del nucleo query legacy

Stato: passi 2-6 implementati sul branch `wf/query-core-completion`; vedi `## Esito`.
Baseline: `90984fb`, versione sorgente 0.4.0; 683 test, copertura 95%.
Riferimento legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.

## Obiettivo e collocazione

Aumentare la copertura funzionale legacy con parametri collezione, DISTINCT,
GROUP BY/HAVING e count, preservando l'architettura modello → piano → dialetto →
driver → execute. Prima verificare i difetti concreti; la documentazione segue
il comportamento implementato, non costituisce il primo intervento.

È un incremento F3 del piano 15, preceduto dal sottoinsieme F2 necessario alle
nuove clausole. Non chiude automaticamente F2, tutta F3 o V1. Restano fuori dalla
chiusura di questo incremento relationDict, joinConditions, relazioni to-many,
Selection/Bag, wildcard su relazioni e il contratto completo di ordinamento,
pkey implicita e alias legacy. Le interazioni necessarie con questi aspetti
vanno però risolte o esplicitamente rifiutate, non ignorate.

## Regole di esecuzione

Per ogni passo: sorgente legacy → caso eseguibile → test di regressione nuovo
fallente → implementazione → confronto PostgreSQL/SQLite → aggiornamento delle
sole pagine interessate. Un difetto legacy osservato non diventa automaticamente
un requisito: registrare la differenza e la decisione sul comportamento nuovo.

Niente cache, pool, framework per backend, cambio dei lock SQLite, nuova entità
sessione o runtime async in questa fase. Correggere un difetto architetturale
solo se ostacola un contratto incluso, con evidenza del problema e test.
Non modificare l'isolamento per thread o i confini commit/rollback.

## Passo 1 — Diagnosi e contratti osservabili

- Riprodurre i rilievi dell'analisi che toccano le query: IN con liste, alias
  automatici, wildcard, opzioni rifiutate, compilazione ripetuta e binding env.
  Classificarli come bug, funzionalità assente o scelta intenzionale.
- Leggere SqlQuery.count/compileQuery, SqlQueryCompiler.compiledQuery e il
  trattamento dei parametri negli adapter legacy. Eseguire i percorsi originali
  in fixture isolate, indicando chiaramente eventuali stub e limiti delle prove.
- Salvare una matrice di input, risultati, nomi/tipi delle colonne, errori e
  SQL/parametri prodotti. Distinguere conteggio delle righe, dei valori distinti
  e dei gruppi; verificare limit/offset, HAVING e query aggregate senza GROUP BY.
- Fissare il contratto di IN/NOT IN per liste e tuple, collezioni vuote,
  duplicati, None nella collezione e colonna NULL. Verificare il trattamento
  delle stringhe scalari senza convertirle implicitamente in liste di caratteri.
- Verificare con esempi la forma legacy di distinct e group_by, inclusi eventuali
  valori speciali. Non promettere tutte le forme perché il parametro esiste.
- Riprodurre pochi benchmark locali con script, dataset e configurazione salvati:
  compilazione semplice/complessa, riesecuzione della stessa query e count.
  Servono al confronto finale, non autorizzano ottimizzazioni speculative.

**Uscita:** matrice dei contratti con fonti e prove; decisioni semantiche fissate
prima dell'implementazione dipendente. Un'incompatibilità sostanziale non coperta
dalle scelte già accettate va portata all'utente con un caso concreto.

## Passo 2 — Prerequisiti minimi del modello e del piano

- Verificare che colonne, alias, formule e path to-one già supportati possano
  essere risolti uniformemente nelle nuove clausole, senza accesso al DB.
- Controllare che i nomi fisici e gli alias di join restino coerenti e che una
  relazione ripetuta non produca join duplicati o parametri in collisione.
- Estendere QueryPlan con clausole strutturate per raggruppamento e distinzione;
  mantenere i valori separati dal testo SQL e il formatter indipendente dal modello.
- Definire i rifiuti per combinazioni non valide, per esempio locking insieme
  a raggruppamenti/distinct, secondo i backend. Non affidarsi alla permissività
  SQLite per dichiarare una query portabile.

**Uscita:** test del piano e dei due dialetti, risoluzione delle clausole coerente
con SELECT/WHERE, errori espliciti. Nessuna riscrittura generale del modello F2.

## Passo 3 — Parametri collezione IN / NOT IN

Sintassi applicativa da coprire:

```python
query = db.table('sales.invoice').query(
    where='$id IN :ids', params={'ids': [1, 2, 3]},
)
```

- Supportare IN/NOT IN con binding dei singoli valori, secondo la matrice del
  passo 1, su PostgreSQL e SQLite. Nessuna interpolazione di dati nel testo SQL.
- Gestire in modo semanticamente corretto la collezione vuota: non generare IN ().
- Preservare stringhe SQL, commenti, identificatori quotati e cast; non riscrivere
  un IN testuale contenuto in essi. Evitare collisioni con parametri già presenti.
- Verificare lo stesso parametro usato più volte, più collezioni nella query,
  parametri ambientali, valori ostili e riuso della query con ambiente mutato.
- Verificare WHERE, HAVING e sottoquery incluse; per raw update/delete applicare
  la stessa grammatica dove il compilatore condivide il percorso di espressione.
  Un uso ambiguo della stessa collezione in posizione scalare va rifiutato.
- Preservare la sintassi PostgreSQL ANY già funzionante. Tuple di colonne e
  liste di tuple composite non entrano implicitamente nel contratto.

**Uscita:** risultati conformi al contratto anche con vuoto/NULL, test reali sui
due backend e verifica che nessun valore finisca interpolato nel testo SQL.

## Passo 4 — DISTINCT, GROUP BY e HAVING

```python
query = db.table('sales.invoice').query(
    columns='$customer_id, SUM($total) AS total',
    group_by='$customer_id',
    having='SUM($total) >= :minimum',
    params={'minimum': 100},
    order_by='$customer_id',
)
```

- Portare le opzioni dal livello SqlTable.query al piano e ai due renderer.
- DISTINCT deve distinguere la proiezione richiesta: verificare che colonne
  implicite, chiavi o flag di policy non ne alterino la cardinalità.
- Risolvere riferimenti, formule e relazioni nelle clausole; mantenere parametri
  di HAVING separati e metadati coerenti per le proiezioni aggregate.
- Verificare ordine, limit/offset, alias espliciti, join to-one, gruppi NULL,
  dataset vuoto, formule/subquery correlate già ammesse e policy di riga.
- I casi non supportati devono fallire chiaramente; niente emulazione di gruppi
  o deduplicazione delle righe in Python. DISTINCT ON non è incluso salvo
  decisione esplicita emersa dalla matrice iniziale.

**Uscita:** uguaglianza di risultati e metadati attesi sui casi portabili,
con differenze di tipo/ordinamento native dei backend esplicitamente registrate.

## Passo 5 — Terminale query.count()

- Restituire un intero mediante SQL, senza fetch di tutte le righe o gruppi.
- Query ordinaria: contare le righe selezionate. Query DISTINCT: i risultati
  distinti. Query raggruppata: i gruppi superstiti a HAVING.
- Fissare nel passo 1 se e come limit/offset influiscono sul terminale; non
  assumere che count significhi sempre la dimensione della pagina corrente.
- Trattare esplicitamente query aggregate senza GROUP BY, dataset vuoto,
  proiezioni correlate, policy, ordine e for_update. Non perdere i join che
  influiscono sul risultato né mantenere clausole superflue o invalide.
- Usare il piano comune e, quando necessario, una sottoquery di conteggio.
  Rispettare ambiente, connessione nominata, binding ed esecuzione centralizzata.
- Non mutare l'oggetto query: count seguito da fetch deve mantenere la query
  originale, comprese opzioni e parametri. Nessun commit implicito.

**Uscita:** count corretto per tutte le forme ammesse dalla matrice, verificato
con risultati noti e controllando che il DB restituisca soltanto il conteggio.

## Passo 6 — Accettazione integrata e consegna

Fixture condivisa: clienti con e senza fatture, totali duplicati, righe NULL,
fatture draft/eliminate, almeno due organizzazioni e nomi fisici rimappati.
Verificare le combinazioni di collezioni, join, formule, raggruppamenti, HAVING,
DISTINCT, count, paginazione e cambi di currentEnv. Ordinare esplicitamente i
confronti quando il contratto non garantisce un ordine naturale.

- Eseguire l'intera suite PostgreSQL/SQLite senza skip inattesi, controlli di
  stile/tipi, demo e prove legacy incluse nella matrice.
- Ripetere i benchmark del passo 1 e spiegare le regressioni significative:
  nessuna soglia inventata sui numeri del report esterno.
- Controllare la portabilità async secondo il documento 26: nessun I/O in
  compilazione o proprietà passive; count è un terminale I/O con futuro
  corrispondente async, senza introdurre ulteriori vincoli di thread.
- Aggiornare guide query/compiler/limitations, esempi eseguibili, note di rilascio
  e piano 15 solo sulla base delle capacità effettivamente verificate.
- Fare commit coerenti per passo completato; riesame finale prima della consegna.
  Tag e pubblicazione PyPI restano un'operazione separata.

**Chiusura:** tutti i passi e la matrice accettati, nessun bug bloccante incluso
rimasto aperto, errori supportati/non supportati documentati sul posto. Segnalare
come concluso questo incremento, mantenendo visibili i residui F2/F3/F4/F5.

## Esito

Passi 2-6 implementati in quattro fasi sul branch `wf/query-core-completion`.

| Fase | Contenuto | Commit |
|---|---|---|
| 1 | parametri collezione `IN` / `NOT IN`, query compilate e SQL diretto | `d5253d3` |
| 2 | clausole di `QueryPlan` e opzioni DISTINCT, GROUP BY, HAVING | `8ae8392` |
| 3 | terminale `SqlQuery.count()` | `5d0527c` |
| 4 | accettazione integrata, benchmark e documentazione | questo commit |

Suite finale: 844 test passati su PostgreSQL e SQLite, 1 skip
(`= ANY` è sintassi PostgreSQL, saltato su SQLite), copertura 95%. Ruff, mypy e
la build strict della documentazione passano. I 16 test di accettazione del
passo 6 sono passati senza richiedere alcuna correzione in `src/asqueel`.

### Benchmark

Rerun dello script invariato `docs/design/evidence/query_benchmark.py`; risultati
in `docs/design/evidence/query_benchmark_after.json`, confronto sulle mediane
asqueel rispetto a `query_benchmark.json` (stessa macchina, stesse versioni).

| Caso | PostgreSQL prima → dopo | Δ | SQLite prima → dopo | Δ |
|---|---|---|---|---|
| compile_simple | 0.033363 → 0.034012 | +1.9% | 0.034470 → 0.036245 | +5.1% |
| compile_relation_two_subqueries | 0.150561 → 0.150792 | +0.2% | 0.156819 → 0.159912 | +2.0% |
| repeated_fetch_same_query | 0.080987 → 0.081536 | +0.7% | 0.043628 → 0.043634 | +0.0% |
| record_pkey | 0.065831 → 0.063243 | -3.9% | 0.039625 → 0.039427 | -0.5% |
| insert_single_row | 0.058886 → 0.059151 | +0.5% | 0.036404 → 0.036495 | +0.2% |
| fetch_10000_rows_to_one_join | 0.019931 → 0.018421 | -7.6% | 0.021019 → 0.019866 | -5.5% |

Le uniche variazioni in peggio oltre il 2% sono quelle di compilazione su SQLite:
`compile_simple` +5.1% e `compile_relation_two_subqueries` +2.0%. La causa è la
scansione unica del compilatore, che ora riconosce anche la parola chiave
`IN` / `NOT IN` prima di `:nome` (regex `_PARAM` estesa in fase 1) e valuta le
nuove opzioni `distinct`, `group_by`, `having` in `plan_select` (fase 2): lavoro
per-compilazione aggiunto, nessuna query in più. I casi che toccano il database
non peggiorano in modo significativo: le due diminuzioni su
`fetch_10000_rows_to_one_join` e la diminuzione su `record_pkey` PostgreSQL sono
rumore di misura, come lo erano i run anomali già presenti nella baseline
(`compile_relation_two_subqueries` PostgreSQL ha un run a 0.282938 contro una
mediana di 0.150561). Nessuna soglia è stata inventata.

### Portabilità async (documento 26)

`count()` è un terminale di I/O: esegue una sola statement attraverso
`self.db.execute(compiled)`, come `fetch()`. La compilazione e le proprietà
passive restano senza I/O — `SqlQuery.compiled` e `count()` condividono
`_compile(terminal)`, che non tocca la connessione. Nessun vincolo di thread
nuovo è stato introdotto.

### Residui

Restano aperti e visibili F2/F3/F4/F5 del piano 15. Fuori da questo incremento,
come previsto: R33 oltre la correzione della guida, R34 (espansione `*`),
`relationDict`, `joinConditions`, relazioni to-many, Selection/Bag, DISTINCT ON
e `IN` su tupla di colonne.
