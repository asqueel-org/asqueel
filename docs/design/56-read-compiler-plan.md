# 56 — Piano del compilatore letture: SQL e kwargs

14 ottobre 2026. Aggiornamento dell'[indagine 55](55-select-sql-and-kwargs-investigation.md).
Stato: passo 1 completato e verificato; nessuna implementazione degli
operatori o della concatenazione query → query nel core. Il piano 30 resta la
cronologia dell'incremento già consegnato.

La [checklist 58](58-compiler-checklist.md) dettaglia la copertura corrente
per funzionalità e separa lavoro acquisito, decisioni aperte e rinvii.

**Rinvio concordato il 14 ottobre 2026:** i passi 3 (SELECT FROM SELECT) e 4
(operatori fra query) aspettano. Manteniamo le firme e il piano di verifica
per la ripresa, senza implementarli ora. Prosegue il completamento delle
formule e relazioni nella query singola; i test su catene/composizioni del
passo 7 non sono criteri di chiusura del perimetro corrente.

## Priorità acquisita: formule e test legacy

**Censimento e baseline eseguiti:** [rapporto 59](59-formula-legacy-baseline.md),
con otto riferimenti congelati, risultati per test e limiti delle fixture.
Il primo raccordo è implementato nel [rapporto 60](60-native-sql-formulas.md):
formule SQL, dipendenze, alias e var_*, con 93 test legacy superati e 3 skip
originali SQLite. La copertura completa del corpus resta aperta.

**Decisione del 14 ottobre, successiva alla checklist:** dedicare particolare
attenzione alle formulaColumn nelle loro diverse forme. L'obiettivo corrente
è superare tutti i test legacy pertinenti al compilatore, non fermarsi alle
formule semplici o ai soli test già presenti in Asqueel. Eventuali sintassi
più amichevoli potranno affiancare quelle legacy in seguito; nessuna nuova
firma è approvata da questa intenzione.

Il censimento comprende i branch individuati nel riesame 57; il porting
prosegue per famiglie, distinguendo SQL, sottoquery e formule fornite da metodo. Conservare i numeri dei
passi sotto come riferimenti: il lavoro sulle formule dei passi 5–6 assume
priorità rispetto a nuove composizioni, affrontando i prerequisiti del passo 2
quando necessari. Le catene e gli operatori restano nel piano.

- [x] Fissare revisioni e raccogliere test/fixture su formule SQL, select,
  exists, select_*, var_*, macro, alias, correlazioni, static e tipi di colonna.
  Punti iniziali nel checkout legacy: `gnrpy/tests/sql/test_compiler_coverage.py`,
  `test_compiler_simulation.py`, `e_query_test.py`, `h_query_surface_test.py`;
  cercare anche i casi nei branch e nei modelli applicativi. Inventario completo
  dei candidati e selezione della baseline nel rapporto 59.
- [x] Eseguire la baseline legacy e distinguere test verdi, fallimenti già
  presenti e prerequisiti mancanti, prima di attribuire difetti al porting.
- [ ] Portare gli stessi casi su Asqueel, adattando solo l'allestimento e i
  confini delle API necessari, senza eliminare asserzioni o cambiare i risultati
  attesi per ottenere il verde. Conservare la provenienza di ogni caso.
- [ ] Partire dagli algoritmi legacy e raccordarli al percorso esistente;
  verificare SQL/kwargs, cardinalità, NULL, tipi e risultati PostgreSQL.
  Differenze di alias/binding interni vanno confrontate coerentemente, senza
  richiedere identità testuale quando il contratto è equivalente.
- [ ] Rendere conto di **tutti** i test censiti: superati, falliti, non eseguiti
  o in conflitto con decisioni esplicite. Skip/xfail non valgono come superamento.
  Un conflitto con i rinvii concordati o un difetto legacy richiede un esame
  esplicito; non si risolve cancellando il test o reintroducendo una funzione
  esclusa di nascosto. Non dichiarare parità completa finché restano casi aperti.
- [ ] Solo dopo la compatibilità, presentare eventuali sintassi affiancate
  con esempi equivalenti e gli stessi test di comportamento, per revisione.

Il contratto del compilatore resta SQL e kwargs senza esecuzione; il database
serve nelle prove di equivalenza. Questo obiettivo non estende implicitamente
il lavoro alle suite legacy di UI, scheduler o all'intero runtime GenroPy.

Il [riesame 57](57-legacy-compiler-refactoring-review.md) verifica i refactor
di febbraio e le conversazioni SQL archaeology di settembre. Distingue i
precedenti riutilizzabili dagli esperimenti semantici non acquisiti nel piano.

## Contratto acquisito

- Si parte dalla chiamata `table.query(...)` legacy, con clausole testuali e
  parametri. La grammatica Builder delle clausole resta rinviata.
- L'uscita è **SQL di lettura e kwargs coerenti con tutti i placeholder**,
  senza esecuzione, apertura di connessioni o interpolazione dei valori nel SQL.
  Per PostgreSQL si conserva l'uscita pronta per il driver già presente.
- Si include `table.query(...).query(...).query(...)`: ogni chiamata successiva
  costruisce una SELECT il cui FROM è la query precedente. Non esegue risultati
  intermedi e non aggiunge implicitamente una UNION.
- Ogni livello vede le colonne esposte dal precedente e può aggiungere join
  tramite le relazioni delle colonne proiettate. Caso richiesto: se il livello
  interno espone il campo relazionale `customer_id`, quello esterno può usare
  `@customer_id.name`. Il compilatore deve conservarne l'origine nel modello,
  non tentare di indovinare la relazione dal nome della colonna.
- Si includono composizioni di query sulla stessa tabella con gli operatori
  del branch GenroPy `feature/compound_query`:

  | Espressione | Operatore SQL | Duplicati |
  | --- | --- | --- |
  | `q1 + q2` | `UNION` | Eliminati |
  | `q1 \| q2` | `UNION ALL` | Conservati |
  | `q1 & q2` | `INTERSECT` | Eliminati |
  | `q1 - q2` | `EXCEPT` | Eliminati |

  Sono operazioni sulle righe proiettate secondo la semantica PostgreSQL,
  non riscritture sulle sole pkey o fusioni delle condizioni WHERE.
  Le proiezioni devono essere compatibili per posizione, numero e tipo.
- Il riferimento di estrazione resta l'API esistente: acquisire una sola volta
  `compiled = q.compiled`, quindi `compiled.sql` e `dict(compiled.params)`.
  La query composta dovrà offrire la stessa uscita completa. Nessuna nuova firma
  pubblica del compilatore viene decisa qui.

## Query concatenate e relazioni sulle colonne esposte

Esempio di sintassi obiettivo, ancora da implementare. Si assume una tabella
con `customer_id` collegato a customer, e customer con una colonna `name`:

```python
q = tbl.query(
    columns='$customer_id, SUM($total) AS totale',
    group_by='$customer_id',
).query(
    columns='$customer_id, @customer_id.name AS customer_name, $totale',
    where='$totale > :soglia',
    soglia=1000,
)

compiled = q.compiled
sql = compiled.sql
kwargs = dict(compiled.params)
```

La prima SELECT produce `customer_id` e `totale`. La seconda usa questa SELECT
come tabella derivata e genera il join verso customer **nel livello esterno**,
partendo dal suo `customer_id`. Il tipo e le condizioni del join seguono le
regole di relazione già presenti, da verificare sul legacy; non si stabilisce
qui un nuovo default INNER/LEFT JOIN o una nuova cardinalità.

Il requisito comporta che la descrizione interna delle colonne proiettate
conservi, dove riconoscibile, il collegamento al campo e alla relazione del
modello. Non è un nuovo attributo della source, un contenitore metadata pubblico
o una configurazione da scrivere a mano. `totale` resta il risultato aggregato;
la chiave diretta raggruppata `customer_id` mantiene l'origine relazionale.

Ogni ulteriore `.query(...)` applica la stessa regola. La compilazione deve
risolvere `$campo` e `@relazione.campo` nel livello corretto, mantenere distinti
alias SQL e binding, e consegnare una sola coppia SQL/kwargs per tutta la catena.
I join esterni non devono essere spostati nella query interna: potrebbero
cambiare aggregazioni, limiti e numero delle righe.

Per il primo caso acquisito basta un campo relazionale proiettato direttamente
con il suo nome. Vanno censiti e presentati prima di estendere il comportamento:
rinomina della chiave con AS e nome da usare nel path, nomi esposti duplicati,
espressioni calcolate chiamate `customer_id`, provenienze diverse dopo UNION e
relazioni che richiedono ulteriori campi non esposti dalla query interna.
Non attribuire relazioni per somiglianza dei nomi, né aggiungere di nascosto
colonne alla proiezione per rendere valido un path. Un riferimento privo dei
campi o dell'origine necessari deve essere diagnosticato esplicitamente.

## Riferimento legacy e prova riproducibile

Implementazione del 16 febbraio 2026:
[c0d1004b8e](https://github.com/genropy/genropy/commit/c0d1004b8eb0548d01f92cdf886dd90e36867609),
test [4c075f7ada](https://github.com/genropy/genropy/commit/4c075f7adac55c05f2dad555b2b1277449388944).
La stessa implementazione compare il 19 febbraio in `fc4021c6ab`.
File: `gnrpy/gnr/sql/gnrsqldata/query.py`, `compiler.py` e
`gnrpy/tests/sql/test_compound_query.py` nel repository GenroPy.

La [sonda documentale](probes/legacy_compound_query.py) legge con `git show`
il commit fisso `4c075f7ada`, estrae senza riscriverli i metodi di composizione,
cache, `mangle` e `mangleParams`. Sostituisce con una fixture minima solo la
costruzione delle foglie e il percorso modello → SELECT. Non importa Asqueel,
non modifica GenroPy e **non è una verifica dell'intero compilatore legacy**.

```sh
python3 docs/design/probes/legacy_compound_query.py \
  --legacy /Users/gporcari/Sviluppo/Genropy/genropy \
  --postgres --output /tmp/asqueel-compound-postgres.json
```

La connessione legge `GNR_TEST_PG_HOST/PORT/USER/PASSWORD` come i test del
repository, con i default locali; usa il database `postgres`. Ogni confronto
esegue `PREPARE`/`EXECUTE` su costanti in una transazione `READ ONLY` e termina
con rollback, senza creare tabelle o schemi. La sostituzione dei placeholder
della fixture con `$1`, `$2` serve solo alla prova PostgreSQL; non è un adapter.
Senza `--postgres` esegue esclusivamente i controlli strutturali.

Esecuzione su **PostgreSQL 17.7: 50 confronti, 40 conformi e 10 divergenze attese**.
La sonda termina con successo solo se riconosce esattamente queste divergenze.
Sono stati confrontati anche i duplicati, non solo gli insiemi degli ID.
Il primo tentativo di connessione era bloccato dalla sandbox; la prova completa
è stata eseguita con accesso locale autorizzato.

### Riuso e cache

`_compound` assegna `mangler` alle query originali; i composti ne conservano i
riferimenti. `_get_compiled` conserva invece in cache la prima compilazione
della foglia, senza invalidarla quando cambia `mangler`.

Controesempio verificato:

```python
# Foglie della sonda: SELECT :n AS x, con n=1 e n=2.
q1.sqltext          # Compila q1 prima della composizione.
q = q1 + q2
sql, kwargs = q.test()
```

Il SQL ottenuto è `SELECT :n AS x UNION SELECT :cq1_n AS x`, con
`{'n': 2, 'cq1_n': 2}`. Il merge dei parametri ha sovrascritto `n=1`:
PostgreSQL restituisce `[2]` invece di `[1, 2]`. Il difetto si riproduce anche
compilando entrambe le foglie prima della composizione.

Creare `a = q1 + q2` e poi `b = q1 + q3` modifica il prefisso di q1 anche
dentro a. Nei casi provati, con foglie non compilate in precedenza, entrambi
i risultati sono corretti: la mutazione è reale, ma non implica un risultato
sbagliato in ogni riuso. Anche il riuso dopo la compilazione di un composto e
le quattro operazioni di una query con se stessa passano nelle fixture provate.

Un altro limite osservato direttamente: `SqlCompoundQuery.compiled` restituisce
il compiled della prima foglia, mentre `sqltext` costruisce l'intero composto.
Non va copiato nel contratto Asqueel, dove SQL e kwargs sono nello stesso compiled.

### Raggruppamenti e clausole delle foglie

Il ramo composto-op-semplice concatena il template precedente senza racchiuderlo.
Con `INTERSECT` PostgreSQL può quindi interpretare un altro raggruppamento:

```python
q = (q1 + q2) & q3
```

Diventa `SELECT … UNION SELECT … INTERSECT SELECT …`, cioè
`q1 UNION (q2 INTERSECT q3)`, anziché `(q1 UNION q2) INTERSECT q3`.
La fixture q1=`[1,2,2]`, q2=`[2,3]`, q3=`[2]` restituisce `[1,2]`
anziché `[2]`. Lo stesso difetto compare con `UNION ALL` e `EXCEPT` a sinistra
di `INTERSECT`. Non basta affidarsi alla precedenza degli operatori SQL.

| Gruppo di prove | Esito |
| --- | --- |
| 16 combinazioni `(a op b) op c` | 13 conformi; 3 divergenze con INTERSECT esterno |
| 16 combinazioni `a op (b op c)` | Tutte conformi |
| Due composti, combinati con ciascuno dei 4 operatori | Tutte conformi |
| Riuso prima/dopo la compilazione del composto; operazioni con se stessa | 7 conformi |
| Foglia sinistra o entrambe le foglie già compilate separatamente | 2 divergenze sui parametri |
| ORDER BY, LIMIT, ORDER BY/LIMIT/OFFSET sulla foglia sinistra | 3 errori di sintassi; riferimenti parentetizzati validi |
| ORDER BY/LIMIT, con o senza OFFSET, sulla foglia destra | 2 divergenze: la clausola si applica al composto |

Le parentesi devono quindi conservare sia i gruppi costruiti in Python sia
l'ambito delle clausole di ogni SELECT. Nel caso destro, senza parentesi,
`a UNION b ORDER BY x LIMIT 1` limita l'intera UNION: la fixture restituisce
`[1]` invece di `[1,2]`. Non tutti i difetti producono un errore di sintassi.
Un ordinamento del risultato composto
non è stato deciso: non reinterpretare come globale l'ordine di una foglia.

## Sequenza di implementazione proposta

### 1. Fissare il contratto SQL/kwargs della singola query

**Completato il 14 ottobre 2026.** Riutilizzato il percorso esistente
`query.compiled → compiled.sql / dict(compiled.params)`, senza nuove API.
I test sul modello nativo impediscono esplicitamente connessioni ed esecuzione
durante la compilazione. Coprono CASE/COALESCE, join, date e Decimal, collection,
collisioni dei binding, riuso della query e cambi di environment.

Portati gli algoritmi `expandInRange` e `expandPeriod` di
`gnrpy/gnr/sql/gnrsqldata/compiler.py` (riferimento `compiler_next_step_1`,
`12cfdcce86337119591b6c8247e7166d831c08b9`), nei contesti legacy pertinenti:
`#IN_RANGE` nel WHERE e nelle formule SQL già supportate; `#PERIOD` nel WHERE,
anche delle sottoquery già supportate. Nessun registro di macro nuovo.
La decodifica dei periodi riusa `genro_toolbox.dates.parse_period`:
dipendenza e lock aggiornati a Toolbox 0.17.0. Verificati periodi inglesi e
italiani, date singole, intervalli aperti/chiusi e periodi vuoti; non si dichiara
equivalenza completa del parser per ogni locale e caso del legacy.

Adattamenti motivati e verificati:

- In `#IN_RANGE` i confronti tipizzati precedono i controlli NULL: PostgreSQL
  altrimenti rifiuta alcuni parametri nulli con `AmbiguousParameter`. Restano
  i quattro casi legacy e la stessa logica a tre valori, anche per valori NULL.
- I nomi `period_from`/`period_to` non sovrascrivono parametri del chiamante:
  usano la gestione dei nomi e degli scope già presente.
- Stringhe SQL e commenti sono protetti dall'espansione delle macro attraverso
  la scansione lessicale già presente. Le macro non supportate danno un errore
  esplicito; non vengono interpretate in nuovi contesti.

`#THIS`, `:env_*` e le sottoquery nominate conservano il percorso esistente.
`#ENV`, `#PREF`, BAG e TS/VEC restano fuori da questo incremento; il raccordo
delle formule native resta al passo 5. Il compiler diretto con environment
minimo richiede `workdate` e `locale` per `#PERIOD`, senza default aggiunti.

Verifiche: regressioni mirate **463 passati, 1 saltato**; suite completa
**1350 passati, 1 saltato**, inclusi PostgreSQL 17.7 e SQLite. Suite completa
eseguita con `PYTHONPATH=src:../asqueel-migration/src`, usando il migratore
del workspace come nelle verifiche del modello. Toolbox è la distribuzione
pubblicata 0.17.0, senza dipendere dal checkout Toolbox o da GenroPy.
Test aggiunti: `tests/native_compiler/test_compile_only.py` e
`tests/native_compiler/test_query_macros.py`. I secondi eseguono il SQL solo
nelle fixture di verifica; il percorso di compilazione resta senza I/O.
Ruff sui file Python modificati e mypy sui 50 file sorgente passano.
Documentazione Sphinx compilata con `-W --keep-going`, senza warning.

Usare l'API esistente, con CASE/COALESCE, parametri tipizzati, collection ed
environment. Verificare che la compilazione non apra connessioni e che il
risultato contenga insieme SQL e valori pronti per il driver. Conservare la
ricompilazione nell'ambiente corrente già presente in Asqueel, senza importare
la cache legacy incidentalmente.

**Chiusura:** test di corrispondenza placeholder/valori, collisioni e query
riutilizzata; nessuna nuova API necessaria per estrarre la coppia.

### 2. Raccordare il modello nativo alle letture di base

Collegare le options già espanse ai filtri di lettura legacy e correggere
l'espansione di `*`, secondo l'indagine 55. Nessuna nuova option o riespansione
della source. Separare i default ancora da confrontare (pkey implicita, ordine
di tabella, alias automatici) dai comportamenti già concordati.

**Chiusura verificata nel [rapporto 65](65-native-options-and-star.md):** query
fisiche e filtri sui 74 modelli, PostgreSQL e SQLite. `*` compila su 73/74:
`adm.htmltemplate_atc` richiede ancora pyColumn statiche. Partition nativa
limitata al valore corrente scalare, come concordato; insiemi ammessi rinviati.

### 3. Concatenare SELECT FROM SELECT, con join nel livello esterno — rinviato

Prerequisito: applicare il riesame 57 al percorso attuale. `Projection.column`
e `ResultColumn.source` conservano già l'origine dei riferimenti diretti:
verificare prima queste informazioni, senza introdurre un registro parallelo.
I branch v2 separano risoluzione e alias ma non forniscono già un modello di
proiezione navigabile pronto per questa firma.

Aggiungere la `.query(...)` sull'oggetto query come richiesto. Il livello esterno
si risolve sulla proiezione della query precedente, non su tutte le colonne
della tabella iniziale. Collegare questa sorgente derivata al percorso esistente
di risoluzione dei campi, relazioni e binding, senza introdurre un secondo
compilatore o una nuova grammatica delle clausole.

La risoluzione di un campo relazionale deve collegare la relazione del modello
di origine al nome effettivamente esposto dal FROM derivato. Usare questo stesso
percorso nelle clausole già supportate (columns, where, order_by, group_by,
having), evitando una risoluzione separata valida soltanto per le proiezioni.

Procedere da due livelli con sole colonne esposte al caso `@customer_id.name`,
quindi a tre livelli e ai parametri omonimi con valori diversi. La provenienza
del campo relazionale deve attraversare le proiezioni dirette successive; il
join va generato nel livello che lo richiede, usando la chiave esposta dal FROM
derivato. Conservare i limiti e i raggruppamenti di ogni SELECT e non mutare la
query interna quando si costruiscono due query esterne diverse.

Confrontare con il legacy la risoluzione dei path e le condizioni di join,
senza attribuirgli la nuova firma concatenata non ancora verificata. Controllare
inoltre il trattamento dei filtri impliciti sulle tabelle coinvolte: non
riapplicare alla tabella derivata i filtri della tabella originaria alla cieca.
Le varianti ambigue elencate sopra richiedono una decisione prima del supporto.

**Chiusura:** verifiche senza I/O della coppia SQL/kwargs e confronti PostgreSQL
per aggregazione interna e join esterno, chiavi NULL/relazioni mancanti secondo
le regole vigenti, path richiesto più volte, parametri omonimi fra livelli,
catena di tre query e riuso della query interna. Verificare che LIMIT/OFFSET
restino al loro livello e che colonne non esposte o origine non riconoscibile
non ricadano silenziosamente sulla tabella iniziale.
Includere due relazioni distinte verso la stessa tabella, join richiesto in
WHERE/ORDER BY oltre che in columns e assenza di segnaposto interni nel SQL finale.
Non trasferire in questo passo gli aggregatori automatici o la conversione
sottoquery → join dei branch sperimentali.

### 4. Aggiungere la composizione con gli operatori legacy — rinviato

Lavorare dapprima sulle SELECT fisiche già compilabili, senza attendere tutte
le formule native. Conservare la struttura binaria della composizione fino al
render SQL; non appiattire stringhe già preparate per il driver.

Indicazioni tecniche interne, da concretizzare sul codice esistente:

- Comporre senza modificare opzioni, parametri, prefissi o stato delle query
  originali. Una foglia può ricorrere più volte, anche in composti diversi.
- Compilare i rami con scope distinti nell'allocazione dei parametri esistente;
  produrre SQL e kwargs insieme. Verificare i nomi disponibili in tutti i rami,
  compresi collection, formule, sottoquery e parametri `env_*` espliciti.
  Evitare il `dict.update` di dizionari con nomi ancora in collisione.
- Usare un ambiente coerente per tutta una compilazione composta, mantenendo
  la semantica corrente della ricompilazione alla richiesta successiva.
- Integrare la composizione nel percorso piano → dialetto → driver esistente:
  il driver prepara il risultato completo una volta sola. Non riscrivere con
  regex SQL già formattato come `%(nome)s`, né duplicare l'escape dei percentuali.
- Rendere espliciti i raggruppamenti e l'ambito di ORDER BY/LIMIT/OFFSET delle
  foglie. Conservare l'ordine degli operandi di EXCEPT e la distinzione UNION/ALL.
- Verificare compatibilità di tabella, contesto DB/dialetto e proiezioni.
  Non inventare cast o allineamenti automatici delle colonne. La compilazione
  senza I/O non può certificare tutti i tipi delle espressioni SQL libere:
  distinguerne i controlli locali dalla verifica semantica di PostgreSQL.
- Non restituire come compiled l'oggetto di una sola foglia; mantenere coerenti
  anche la descrizione delle colonne di risultato e i binding del composto.

**Chiusura:** i controesempi di questa indagine diventano test che devono
passare nel core nuovo, con i risultati parentetizzati attesi. Aggiungere
NULL/duplicati, insiemi vuoti, parametri omonimi con valori diversi, collection
e collisioni fra prefissi, ripetizione della stessa query e ricompilazione.
Verificare gli errori per operandi/proiezioni incompatibili e clausole di lock
non combinabili. PostgreSQL è il riferimento richiesto; mantenere verde SQLite
e dichiarare esplicitamente eventuali casi composti non supportati dal dialetto.

### 5. Collegare formule native e var_*

**Primo incremento completato:** [rapporto 60](60-native-sql-formulas.md).
Formule SQL, dipendenze, alias e binding locali usano il percorso esistente;
nessuna nuova sintassi. Raccordati anche i metodi `sql_formula_<nome>(attr)`:
[rapporto 62](62-native-method-formulas.md). Non dichiarare chiuso il passo
completo: restano altre macro, composizioni e dipendenze da relazioni del passo 6.

Tradurre gli attributi degli oggetti completi usando il percorso esistente:
formule SQL, alias, valori locali e due usi della stessa formula. Estendere
anche alle query composte i test dei binding. Nessuna valutazione Python dei risultati o
nuovo resolver introdotti per aggirare dichiarazioni ancora non supportate.

**Chiusura:** formule e var_* con SQL/kwargs completi, senza contaminazione
fra colonne; copertura di tutti i relativi casi del corpus legacy censito,
non soltanto formule semplici. Le verifiche sui rami composti si completano
quando è disponibile il passo 4; non bloccano il porting iniziale delle formule.

### 6. Completare sottoquery e relazioni nel perimetro concordato

**Raccordo select/exists/select_* completato:** [rapporto 61](61-native-subqueries.md).
Riutilizzata la SELECT comune anche per GROUP BY/HAVING/DISTINCT; default
ignorePartition riallineato al legacy. Inverse ordinarie e cinque child_count
raccordate nel [rapporto 63](63-native-inverse-relations.md). subQueryColumn con query dict
raccordate nel [rapporto 66](66-native-subquery-columns.md): semplice su entrambi
i dialetti, JSON/XML su PostgreSQL. Riferimenti stringa a metodi di sottoquery
raccordati nel [rapporto 67](67-native-subquery-methods.md), seguendo la tabella
root della SELECT legacy; XML richiede ancora il dict. bagItemColumn nativa
raccordata su PostgreSQL nel [rapporto 69](69-native-bag-items.md), riusando
formule e binding comuni; nessuna emulazione XPath per SQLite. virtualRelation e
RuntimeModel restano aperti; nessuna conversione
automatica delle sottoquery a JOIN. I metodi di formula SQL sono raccordati nel rapporto 62.

Proseguire con select/exists/select_*, #THIS, clausole e binding annidati;
confrontare i default legacy e le lacune del documento 55. Separare inverse
ordinarie e virtualRelation, rispettando le decisioni già prese sulla GEP.
Nessuna reintroduzione di inverse/limit/order_by/one_one sulle virtualRelation,
aggregateRows, variant o elaborazioni Python dei risultati.

**Chiusura:** casi nativi supportati verificati anche quando presenti in uno
dei rami; elenco esplicito delle dichiarazioni ancora escluse e delle decisioni
necessarie. Non promettere che tutte le virtuali diventino espressioni SQL.

### 7. Verifica finale e documentazione del risultato

Confrontare SQL, kwargs e risultati su PostgreSQL in fixture isolate, includendo
i 74 modelli nativi, le catene SELECT FROM SELECT con join e le composizioni
con operatori. Verificare separatamente che il percorso
di sola compilazione non richieda accesso al server. Eseguire le regressioni
dei dialetti e pubblicare esempi con l'API effettivamente implementata.

**Chiusura:** coppia SQL/kwargs verificata per tutti i casi dichiarati supportati;
report di copertura con esclusioni concrete. La verifica dei risultati usa il DB
nei test, ma non amplia l'obiettivo del compilatore all'esecuzione applicativa.

## Confini ancora validi

SQLGlot resta un controllo finale opzionale da affrontare separatamente:
nessuna integrazione ora. Quel futuro controllo dovrà riconoscere anche
UNION/INTERSECT/EXCEPT leciti, senza scambiare una radice diversa da Select
per una scrittura e senza smettere di controllare tutti i rami e le CTE.
Il prototipo con allowlist minimale del documento 54 non basta per questo.

Non si aggiungono ora nuovi codec JSON/TYTX, una grammatica Builder della query,
metodi dedicati di ordinamento/paginazione dei composti, operatori fra tabelle
diverse, INTERSECT ALL/EXCEPT ALL, scritture o funzionalità di esecuzione.
I controlli e le correzioni sopra sono requisiti del porting, non modifiche
già realizzate. La firma concatenata `.query(...)` è acquisita; la scelta delle
strutture interne non autorizza altre nuove firme. L'innesto su un risultato
di UNION richiede anche la verifica della compatibilità delle origini delle
colonne: non assumere la relazione del primo ramo per tutti gli altri.
