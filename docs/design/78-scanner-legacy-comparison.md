# 78 — Scanner attuale e algoritmi legacy: confronto misurato

14 ottobre 2026. **Non è dimostrato che la sostituzione complessiva sia migliore.**
Il percorso Asqueel evita alcuni errori concreti su testo SQL e parametri, ma
perde convenzioni legacy funzionanti e, con espressioni numerose/ripetute,
compila sensibilmente più lentamente. Queste differenze vanno decise prima di
modificare il compilatore o raccordare le relazioni.

Nessun file di produzione, test esistente o esempio è stato modificato.
Sono stati aggiunti soltanto sonde, risultati e questo rapporto. Il confronto
non approva nuove sintassi e non modifica mixin o RuntimeModel.

## Cosa è stato confrontato

Il legacy di riferimento è `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
Il confronto dinamico usa quel codice originale, non una reimplementazione
semplificata delle sue regex. Asqueel è il working tree corrente, congelato
con le [impronte dei sorgenti](evidence/scanner-comparison/code-before.json).

| Compito | Legacy | Asqueel attuale |
| --- | --- | --- |
| Scoprire i riferimenti | updateFieldDict, COLFINDER e RELFINDER sull'intera stringa | _tokens/_runs distinguono codice, stringhe, identificatori e commenti; expression riconosce i riferimenti nel codice |
| Risolvere i nomi | Dizionario dei riferimenti distinti → getFieldAlias | field/related durante la visita delle occorrenze |
| Sostituire | templateReplace con colPars | Fragment con Identifier e Parameter, poi dialetto e formatter |
| Suddividere colonne e AS | Normalizzazione e gnrstring.split; gestione AS in compiledQuery | _split e _projection_alias, con profondità delle parentesi e token protetti |
| Interpretare i valori dei parametri | embedFieldPars può trasformare stringhe $campo/@relazione in riferimenti | _Bindings li conserva come valori |
| Preparare il protocollo DBAPI | execute e prepareSqlText; adattamento liste, escape e operatori | Formatter dei driver e _Bindings; comportamenti non completamente equivalenti |

**Non tutto ciò che differisce è opera dello scanner.** Escape e operatori
appartengono anche a execute/adattatori; le collisioni sono un tema dei binding.
Non uso questi risultati per attribuire allo scanner meriti o problemi altrui.

Ho inoltre ricontrollato gli otto snapshot già esaminati: i corpi AST di
updateFieldDict, embedFieldPars, templateReplace e prepareSqlText PostgreSQL
sono identici in **8/8**, esclusi i docstring. Le revisioni di execute e
prepareSqlText SQLite non sono tutte identiche. Questo è un confronto statico,
non una riesecuzione completa degli otto branch.
[Impronte e righe](evidence/scanner-comparison/legacy-algorithms.json).

## Metodo e copertura

Un [corpus unico](probes/scanner_corpus.py), con **71 casi e 132 prove**:
63 SQLite e 69 PostgreSQL. Entrambi i motori ricevono gli stessi columns,
where, order_by e parametri, su modelli e dati equivalenti. Quattro fatture,
due clienti, NULL, testo, numeri e nomi problematici; tutti i dati sono sintetici.

La sola opzione di allineamento è `addPkeyColumn=False` nel legacy: serve a
confrontare proiezioni esplicite, senza introdurre la pkey nascosta in Asqueel.
Per provare anche macro e riferimenti già disponibili, il corpus usa il
compilatore Asqueel sul modello precedente. Lo scanner è quello condiviso.
**I benchmark fisici sono eseguiti anche sul nuovo albero**, separatamente.
Non si abilitano macro o relazioni sul nuovo albero per poter fare il confronto.

La sonda conserva SQL prima/dopo la preparazione legacy, kwargs con tipi,
parametri originali dopo la chiamata, righe, nomi delle colonne ed errori.
Chiama il vero execute legacy con un cursore di cattura: in questo modo
include le convenzioni `\:`, `\$` e `\@` senza ricostruirle nel test.
Poi verifica il SQL con psycopg2 per il legacy, psycopg 3 per Asqueel, e SQLite.
Le connessioni di compilazione sono vietate; quelle di verifica sono separate.

SQLite usa database in memoria; PostgreSQL solo tabelle TEMP della sessione,
chiuse al termine. Nessuna modifica a database applicativi. Il caso con
separatore di statement è soltanto compilato, mai eseguito.

Il corpus contiene richieste tratte/adattate da test legacy (colonne fisiche,
parametri, embedFieldPars) e Asqueel (cast, token protetti, alias, collisioni),
più casi limite nuovi. Ogni caso registra la provenienza. **Non è la suite
legacy originale integrale:** i casi sono eseguiti su questa fixture comune,
non sui dati e sul lifecycle di test_invoice. I valori attesi sono dichiarati
indipendentemente dai due compilatori.

Per letterali ed escape, il risultato SQL letterale e la convenzione GenroPy
possono avere intenzioni diverse: uno scostamento dall'aspettativa della sonda
non basta a qualificare il comportamento legacy come bug. La matrice riporta
l'osservazione e conserva le aspettative/provenienza per renderla contestabile.
I numeri delle righe vengono normalizzati per valore nel confronto; i tipi
originali restano registrati. Non si normalizzano i tipi dei kwargs.

## Differenze che impediscono di considerare Asqueel equivalente

### Parametri che rappresentano campi: regressione rispetto al contratto legacy

```python
where = '$quantity > :threshold'
sqlparams = {'threshold': '$unit_price'}
```

- Legacy: WHERE confronta **quantity con unit_price**, come richiedono i test
  TestEmbedFieldPars. Risultato della fixture: fattura 2.
- Asqueel: WHERE confronta quantity con **la stringa '$unit_price'**. PostgreSQL
  fallisce nella conversione a integer; SQLite restituisce un risultato diverso.
- Anche il parametro `@customer_id.id` ha la stessa incompatibilità.

Non è un miglioramento dello scanner: è una convenzione legacy mancante.
Gli algoritmi dei branch sperimentali mantengono embedFieldPars.

### Altre compatibilità perse o modificate

| Richiesta identica | Legacy osservato | Asqueel osservato | Area |
| --- | --- | --- | --- |
| columns='$amount * 2' | Genera l'alias e restituisce i valori | Richiede AS esplicito | Proiezione |
| :codicè con relativo parametro | Funziona su entrambi i DB | Riconosce solo codic e segnala parametro mancante | Regex parametri/formatter |
| WHERE title REGEXP :pattern su PostgreSQL | Traduce in ~* e funziona | SQL non valido | Adattatore |
| WHERE title ILIKE :pattern su SQLite | Traduce in LIKE e funziona | SQL non valido | Adattatore |
| Literal SQL '10%%' su PostgreSQL | Restituisce '10%' secondo l'escape DBAPI legacy | Restituisce '10%%' | Formatter/contratto escape |
| Parametro con valore `r'\$unit_price'` | Il backslash evita embedFieldPars; execute lo rimuove | Il backslash rimane nel valore | Convenzione parametri |
| Literal SQL `'\:id'` | Rimuove l'escape, restituisce ':id' | Conserva il backslash | Convenzione execute |
| Literal SQL '$$' | Template lo riduce a '$' | Restituisce '$$' | Template/letterali |
| Due proiezioni con lo stesso AS | Conserva l'ultima | Errore esplicito | Contratto delle proiezioni |

La riga sugli alias duplicati è un cambio di comportamento, non una
valutazione automatica di quale sia preferibile. Analogamente, preservare
un letterale non autorizza a eliminare le convenzioni di escape esistenti.

## Benefici concreti osservati, da valutare separatamente

| Caso | Legacy osservato | Asqueel osservato | Cosa dimostra |
| --- | --- | --- | --- |
| SELECT '$missing' AS value | Cerca la colonna missing e fallisce | Restituisce il testo '$missing' | Protezione lessicale, se si vuole una stringa SQL letterale |
| SELECT '$id' AS value | Restituisce il testo del riferimento fisico, '"t0"."id"' | Restituisce '$id' | Diversa semantica dei letterali: va concordata |
| Commento contenente $missing o @missing.name | Cerca quei nomi e fallisce | Ignora il contenuto del commento | Beneficio lessicale verificato |
| Literal ':id' e WHERE id=:id su PostgreSQL | Il literal diventa '1' | Il literal resta ':id' | La regex dell'adattatore legacy opera anche dentro stringhe |
| Dollar quote / E-string PostgreSQL del corpus | Errori di campo/split | Restituisce il literal atteso | Copertura di ulteriori forme SQL, non compatibilità totale |
| AS scritto As | SQL con due AS, non eseguibile | Alias riconosciuto | Riconoscimento AS senza distinzione maiuscole/minuscole |
| IN :ids con ids=[1,2] e ids0=3 su SQLite | Espansione sovrascrive ids0 con 1; torna soltanto la riga 2 | Conserva 3 e torna 1,2 | Beneficio reale del binding, non dello scanner |
| Parametro mancante | Errore quando il driver esegue | Errore nella compilazione | Diagnosi anticipata |

Anche quando le righe coincidono, i kwargs non sono necessariamente identici:
nel caso `unused_param` il legacy conserva `unused=99` e aggiunge `jc_kwargs`,
Asqueel inoltra soltanto `id`. Il mapping non vuoto passato alla query legacy
riceve anche `jc_kwargs`; Asqueel lascia invariato quello del chiamante. Sono
differenze osservate, non una nuova decisione sul contratto dell'API.

Il caso di collisione è significativo: non basta confrontare una stringa SQL
plausibile, occorre verificare i kwargs e le righe. La controprova con `ids_0`
passa su entrambi i percorsi. PostgreSQL legacy usa invece tuple per questa IN,
e non presenta la collisione SQLite del caso `ids0`.

Riconoscere token protetti può quindi avere utilità concreta, ma **non dimostra
che sia necessario sostituire getFieldAlias, la mappa dei riferimenti distinti,
embedFieldPars o le altre convenzioni legacy**. Non è stato dimostrato un
vantaggio generale di manutenibilità o di sicurezza dell'SQL.

## Prestazioni

Misura: richiesta nuova → SQL e kwargs pronti per il driver. Stesso processo
Python 3.12.12, modelli già costruiti, 10 warmup, 9 round, ordine dei tre motori
ruotato; GC sospeso soltanto durante le misure. Ogni round usa 100 iterazioni,
30 per le proiezioni da 50/100 campi. Sono esclusi costruzione del modello,
connessione ed esecuzione SQL. Prima del benchmark ogni workload è eseguito
sui tre percorsi e deve produrre valori e nomi di colonna uguali.

Non è un microbenchmark del solo `_tokens`: include proiezione, lookup, piano,
formatter e il piccolo involucro della sonda. È il costo del risultato richiesto
(SQL e kwargs). Il riuso della stessa query cached nel legacy non è misurato;
si creano query nuove in tutti i casi. Non si deduce la latenza applicativa
comprensiva del database da questi tempi.

### postgresql: mediane in microsecondi

| Richiesta | Legacy | Asqueel precedente | Asqueel nuovo albero | Nuovo/legacy |
| --- | ---: | ---: | ---: | ---: |
| 7 colonne distinte | 187.3 | 183.4 | 196.3 | 1.05× |
| SELECT ordinaria, COALESCE e CASE | 170.7 | 232.7 | 231.9 | 1.36× |
| 1 campo | 137.6 | 83.4 | 83.5 | 0.61× |
| 10 proiezioni dello stesso campo | 167.7 | 282.1 | 297.4 | 1.77× |
| 50 proiezioni dello stesso campo | 298.0 | 1198.4 | 1280.8 | 4.30× |
| 100 proiezioni dello stesso campo | 457.6 | 2392.4 | 2614.9 | 5.71× |
| 20 espressioni CASE | 309.9 | 2801.0 | 2732.1 | 8.82× |

### sqlite: mediane in microsecondi

| Richiesta | Legacy | Asqueel precedente | Asqueel nuovo albero | Nuovo/legacy |
| --- | ---: | ---: | ---: | ---: |
| 7 colonne distinte | 204.7 | 187.8 | 200.1 | 0.98× |
| SELECT ordinaria, COALESCE e CASE | 183.4 | 236.2 | 235.6 | 1.28× |
| 1 campo | 146.0 | 84.8 | 83.8 | 0.57× |
| 10 proiezioni dello stesso campo | 182.9 | 281.4 | 300.9 | 1.64× |
| 50 proiezioni dello stesso campo | 353.6 | 1196.2 | 1282.3 | 3.63× |
| 100 proiezioni dello stesso campo | 575.7 | 2342.5 | 2568.9 | 4.46× |
| 20 espressioni CASE | 393.7 | 2633.2 | 2595.1 | 6.59× |


I casi con 50/100 proiezioni dello stesso campo sono sintetici e servono a
misurare le ripetizioni. La SELECT ordinaria e le sette colonne distinte sono
controprove: il confronto non consiste soltanto nel caso peggiore per Asqueel.
I campioni grezzi e una prima misurazione indipendente sono nelle evidenze.
Su un'altra macchina i valori assoluti cambieranno; non sono soglie di SLA.

Il [profilo delle chiamate](evidence/scanner-comparison/profile.json) mostra:

- Una proiezione: 3 chiamate di risoluzione del campo in tutti i percorsi.
- Cento proiezioni dello stesso campo: **3 getFieldAlias nel legacy, 102 field
  nel percorso precedente e 102 nel nuovo albero**.

Il legacy raccoglie i riferimenti distinti in relationDict/colPars prima della
sostituzione. Asqueel risolve le occorrenze durante la scansione; AS e split
aggiungono altri passaggi. Il profilo individua qui una differenza concreta da
riesaminare, senza autorizzare ora una nuova ottimizzazione o una cache diversa.
I conteggi del generatore `_tokens` includono le riprese di yield: non vengono
presentati come altrettante scansioni complete.

## Esito e proposta da discutere

1. **Non approvare il rimpiazzo generale sulla base dei test attuali.** Ci sono
   incompatibilità osservabili e costi peggiori nei workload indicati.
2. Conservare come riferimento l'algoritmo legacy e le sue convenzioni, inclusa
   la risoluzione dei riferimenti distinti; rendere esplicite quelle mancanti.
3. Valutare individualmente una protezione di stringhe/commenti e la prevenzione
   delle collisioni, con i controesempi sopra. Alcune differenze toccano
   convenzioni intenzionali: occorre scegliere il contratto prima di cambiarle.
4. Non procedere ancora con le relazioni. Questa sonda non certifica formule,
   sottoquery, macro complete, RuntimeModel, mixin o compatibilità del runtime.

Verifiche aggiuntive: **294 test esistenti passati**, sui moduli compiler,
compile_only e SELECT gerarchica; Ruff sulle nuove sonde. Non è una nuova suite
integrale del progetto: il codice di produzione è rimasto invariato.

## Evidenze e riproduzione

- [Matrice completa dei casi](evidence/scanner-comparison/matrix.md).
- [Richieste, SQL, kwargs, righe ed errori](evidence/scanner-comparison/results.json).
- [Benchmark con tutti i campioni](evidence/scanner-comparison/benchmark.json).
- [Ambiente e versioni](evidence/scanner-comparison/metadata.json).
- [Verifica finale e impronte](evidence/scanner-comparison/verification.json).
- [Sonda eseguibile](probes/compare_scanners.py), [corpus](probes/scanner_corpus.py),
  [profilo](probes/scanner_profile.py), [inventario legacy](probes/scanner_inventory.py).

```sh
PYTHONPATH=src venv/bin/python docs/design/probes/compare_scanners.py \
  --legacy /tmp/asqueel-formula-baseline/legacy \
  --legacy-site /tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages \
  --out docs/design/evidence/scanner-comparison --postgres --benchmark
```

Le dipendenze legacy mancanti vengono lette dal suo ambiente esistente; nessun
pacchetto è stato installato o aggiornato. Il file code-before.json viene
confrontato a fine sonda con tutti i file Python in src/tests/examples.
