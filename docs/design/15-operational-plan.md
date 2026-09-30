# 15 — Piano operativo di completamento Asqueel

Stato aggiornato al 30 settembre 2026: F1 è **aperta**. Sessioni nominate ed
environment hanno verifiche; i difetti della bozza trigger/deferred censiti nel
[riesame 18](18-interrupted-lifecycle-review.md) sono risolti nella
[consegna 19](19-deferred-lifecycle-fixes.md).
Il [riesame degli errori Python 20](20-python-error-lifecycle.md) verifica 16
scenari per implementazione su PostgreSQL e corregge attribuzione degli errori
fra connessioni e preservazione dell'eccezione originale durante cleanup.
Il controllo successivo del salvataggio legacy conferma che gli errori impediscono
il commit nel percorso normale e che deferredRaise blocca anche il retry.
Il [riesame dei chiamanti 21](21-recovery-callers.md) verifica rollback e ripresa,
log indipendente e salvataggio dello stato di errore: nove scenari per backend.
La protezione nativa resta invariata; il logger senza rollback è un rischio di
porting documentato. Restano retry delle callback, percorsi applicativi indicati
nel riesame e localizzazione completa. Le code pending
sono requisito di chiusura F1 prima di F2; F4 ne integra l'uso nei record/eventi.
F0 dispone di primi oracle, ma il censimento complessivo resta aperto.
Baseline: `2bed211d5c0c2144e4669b9259114757db12e65d`, più documentazione in lavorazione.
Fonti: [audit dei 42 contratti](13-legacy-test-audit.md),
[traguardo e tappe](14-legacy-target-and-stages.md),
[decisioni acquisite](05-decisions.md).

## Obiettivo e regola di lavoro

Consegnare un Asqueel sincrono per nuove applicazioni PostgreSQL, configurato
tramite grammatiche in cascata e utilizzato attraverso gli oggetti vivi:
`db.table('cont.cliente').query(...).fetch()`.
Il legacy guida sintassi, default e lifecycle. Il lavoro parte dal nucleo già
presente: alias, formule e sottoquery correlate vanno completati e integrati,
non riscritti senza un difetto o un requisito preciso.

Per ogni funzionalità: sorgente/test legacy → contratto osservabile → test nuovo
inizialmente fallente → implementazione → verifica PostgreSQL → documentazione
inglese eseguibile. Un comportamento diverso richiede un esempio comparativo e
una decisione esplicita, salvo le differenze già concordate. Non occorre riaprire
le decisioni già acquisite: sincrono, niente aggregateRows, partition esplicita.

Le sigle V1–V4 sotto sono traguardi funzionali, non numeri di versione del package.
Non promettono equivalenza con l'intero framework Genropy.

## Obbligo di tracciabilità completa del legacy

Come richiesto il 30 settembre 2026, nessun aspetto legacy può sparire dal
perimetro di conoscenza perché manca nei test o non entra nella prima versione.
F0 avvia il censimento dell'intera superficie Asqueel; ogni fase lo approfondisce
fino ai singoli contratti della propria area. Le 42 famiglie LT sono l'indice
iniziale, non la granularità finale né una certificazione di completezza.

Il registro deve contenere, per ciascun contratto:

| Campo | Contenuto obbligatorio |
|---|---|
| Identità | API/costrutto, variante, default e contesto applicativo. |
| Evidenza | Sorgente e revisione, test, chiamanti reali; GEP/conversazioni se pertinenti. |
| Semantica | Input/output, tipi, errori, effetti su DB, environment, connessioni, callback ed eventi. |
| Verifica | Caso riproducibile e risultato atteso; distinguere lettura da esecuzione. |
| Destinazione | Nucleo equivalente; nucleo diverso con traduzione compatibile; adapter legacy; esclusione concordata. |
| Differenza | Esempio prima/dopo, limiti dell'adattamento e decisione dell'utente, ove necessaria. |
| Stato | Da analizzare, analizzato, decisione aperta, pianificato, implementato, verificato. |
| Dipendenze | Primitive richieste dal nucleo e fase responsabile della consegna. |

L'adapter legacy qui è il livello di compatibilità con le API e i consumer
Genropy, non l'adapter PostgreSQL o di un altro dialect. Delegare richiede un
contratto concreto e test d'integrazione sul comportamento visibile al chiamante.
Se manca una primitiva interna necessaria, questa resta un requisito del nucleo:
non basta annotare «gestito dall'adapter».

F0 deve censire anche metodi privati semanticamente rilevanti, opzioni non testate,
caricamento package/mixin, hook e percorsi d'errore. Per ogni modulo si registra
lo stato di lettura e si cercano i chiamanti; i punti non chiariti restano aperti.
Prima di chiudere una fase non devono esserci contratti della sua area senza
una destinazione motivata, né differenze introdotte senza accordo. Non si dichiara
«legacy interamente conosciuto» finché il censimento non è chiuso e verificato.

## Sequenza e dipendenze

| Fase | Consegna | Dipende da | Traguardo |
|---|---|---|---|
| F0 | Corpus eseguibile e baseline | — | V1 |
| F1 | Sessione, transazioni ed environment | F0 | V1 |
| F2 | Modello navigabile e metadati | F0 | V1 |
| F3 | Query complete per l'uso quotidiano | F1, F2 | V1 |
| F4 | Record, risultati e lifecycle delle scritture | F1, F3 | V1 |
| F5 | Policy, verticale reale e manuale | F2–F4 | V1 |
| F6 | Relazioni virtuali e formule avanzate | F2, F3, F5 | V2 |
| F7 | Subtables, raccolte e macro | F6 | V2 |
| F8 | Selection, Bag e servizi applicativi | F4, F7 | V3 |
| F9 | Import da DB/package e integrazione migrazioni | F2; F6–F8 per package complessi | V3 |
| F10 | Oggetti SQL nativi, partition fisiche e altri dialect | F9 | V4 |

F1 e F2 sono tecnicamente indipendenti dopo F0. L'integrazione di F3 aspetta
entrambi. Il contratto strutturale di F9 va studiato già in F2 per evitare
modelli impossibili da importare; non serve aspettare V3 per verificarne i nomi.
Nessuna assegnazione ad agenti o esecuzione parallela è avviata da questo piano.

## V1 — Nucleo applicativo quotidiano

### F0 — Rendere misurabile la conformità

- Fissare commit legacy, versioni delle dipendenze e fixture: non usare le
  modifiche locali di test_invoice come baseline implicita.
- Preparare un ambiente legacy isolato e un DB nuovo isolato; i test legacy
  che creano/eliminano database non devono raggiungere database dell'utente.
- Dataset ridotto clienti/stati/fatture/righe con PK 0, valori falsy, NULL,
  FK opzionali, relazioni multiple, draft, deleted e partition.
- Per ogni LT01–LT42 registrare fase, casi sorgente, oracle e stato. Se il test
  legacy è debole, usare un risultato atteso esplicito verificato sul sorgente.
- Eseguire la baseline nuova e i primi casi legacy selezionati; attribuire
  separatamente errori di ambiente, difetti preesistenti e incompatibilità.
- Misurare render/compilazione/esecuzione/materializzazione sul dataset,
  annotando versioni e condizioni. Nessuna soglia arbitraria prima delle misure.

**Uscita:** fixture riproducibile, primi confronti transazioni/path/risultati
eseguibili e registro delle divergenze. Conteggio di test definiti distinto da
raccolti, eseguiti, saltati e superati. Riferimenti: LT01–LT42.

### Attività collaterale C1 — Package legacy → dichiarazione Python

Avviare l'analisi e una prima verticale di traduzione di un package Genropy
reale in sorgente dichiarativo del modello nuovo, con provenienza, dipendenze
e diagnosi delle parti non traducibili. Il [compito 22](22-legacy-package-translation.md)
definisce perimetro e criteri di verifica. Alimenta F2 e anticipa l'importazione
package di F9; non sostituisce la priorità sul nucleo DB né blocca F1.

Il package legacy è una sottoapplicazione con contributi SQL, GUI e altri
servizi. Studiare nel puro SQL import opzionali sull'elemento `db`: i contributi
importati dichiarano schemi, tabelle e colonne tramite le grammatiche esistenti.
Questo punto di composizione dovrà poter accogliere la parte SQL di una futura
sottoapplicazione. Sintassi, collocazione fisica della configurazione e mapping
fra package, namespace logico e schema fisico restano da definire.

### F1 — Transazioni ed environment come nel legacy

- Conservare la transazione implicita del db applicativo e commit/rollback
  espliciti; non richiedere `with db.transaction()` negli esempi ordinari.
- Allineare il comportamento dopo errore SQL al rollback legacy, verificando
  anche il riuso della sessione e gli errori del driver durante la conclusione.
- Esaminare separatamente eccezioni negli hook: il rollback in execute non
  dimostra quale sia il contratto di ogni errore Python.
- Recuperare currentEnv/tempEnv e i default necessari di workdate/locale;
  stabilire mutazione, rimozione e ripristino annidato sulla base del legacy.
- Recuperare le connessioni nominate indipendenti allo stesso database:
  nel legacy la cache è per thread e coppia (storename, connectionName).
  Cambiare `connectionName` tramite tempEnv seleziona una connessione distinta,
  aperta al primo uso; uscire dallo scope ripristina la selezione senza commit
  implicito. Questo requisito non dipende dal futuro supporto store/tenant.
  Separare transazioni, stato di errore e callback per connessione; verificare
  che commit/rollback di B non concludano la transazione pendente di A.
  Le sessioni nominate sono presenti; completare e verificare le code per nome.
- Completare deferred, stack trigger e contesto onCommittingStep, con oracle
  legacy e test sui percorsi di errore prima di avanzare a F2.
- Tenere distinta la convenience del runtime a basso livello dalla sessione
  applicativa; correggere insieme manuale ed esempi.

**Uscita:** due scritture seguite da errore non lasciano dati parziali; visibilità
prima/dopo commit verificata da un'altra connessione; scope env ripristinati
anche su eccezione; nessuna regressione dei valori 0/False. LT26–LT27.

### F2 — Un solo modello risolto per compiler e applicazione

- Verificare composizione della configurazione, grammatiche montate, override
  e rendering; preservare provenienza dei contributi dove necessaria.
- Rendere coerenti column('name'), column('$name') e
  column('@customer_id.@state_id.name'), alias e originalColumn.
- Esporre relazioni dirette/inverse, cardinalità e metadati; il lookup non
  deve eseguire query. Distinguere errore di relazione da colonna assente.
- Fissare classificazione fisiche/virtuali/statiche e comportamento di `*`.
- Verificare mapping schema/prefisso/sqlname e metadati UI: stessa identità di
  colonna, anche quando le informazioni sono dichiarate in un'entità collegata.
- Esplicitare il confine tra grafo delle relazioni disponibile e operazioni
  many non ancora eseguibili; non produrre ricomposizione implicita delle righe.

**Uscita:** stesso path risolto da modello e compiler, metadati corretti attraverso
alias, nomi fisici prevedibili e prova di grammar estesa con rendering. LT01–LT06,
LT09; contratto strutturale iniziale LT02/LT37.

### F3 — Query e forma dei risultati

- Implementare count, DISTINCT, GROUP BY/HAVING e interazioni con ordine,
  limit/offset secondo gli oracle; non simulare count scaricando tutte le righe.
- Ripristinare i contratti IN/NOT IN con collezioni, incluse vuote, NULL e
  stringhe scalari. Conservare il binding del driver, senza interpolare valori.
- Allineare alias automatici, pkey implicita, table order e wildcard su path.
- Integrare relationDict e joinConditions nel profilo verificato; rinviare
  esplicitamente le combinazioni many dipendenti dalle raccolte di F7.
- Verificare formule e sottoquery già implementate nelle nuove clausole.

**Uscita:** uguaglianza di valori, chiavi e tipi dei risultati su casi con
join/duplicati/gruppi; conteggi corretti; errori espliciti sui casi non supportati.
LT11–LT18. Il passaggio di parametri come riferimenti a colonne, LT21, richiede
prima una decisione sul confine fra riferimento intenzionale e dato esterno.

### F4 — Record, terminali e scritture

- Completare record per PK/condizione, ignoreMissing/ignoreDuplicate e
  terminali essenziali fetchPkeys/fetchAsDict; verificare accesso alle righe
  per nome e indice secondo il contratto scelto dal legacy.
- Completare generazione chiavi e gestione old_record; stabilire il profilo
  bulk/raw e documentarne esplicitamente il rapporto con gli hook.
- Usare il nucleo deferToCommit/deferAfterCommit verificato in F1, con ordine, deduplicazione e
  comportamento in caso di rollback o fallimento del callback.
- Verificare lock, record non trovato e update concorrenti senza perdere
  atomicità. Gli eventi non devono annunciare scritture non confermate.

**Uscita:** una scrittura multipla applicativa atomica, hook nell'ordine atteso,
callback prima/dopo commit verificati e terminali con casi mancanti/duplicati.
LT22–LT23, LT28–LT29. Bag/Selection e record cluster completi seguono in F8.

### F5 — Policy e prima consegna utilizzabile

- Integrare draft/deleted/mark e partition con query, record, formule e CRUD.
- Mantenere la semantica partition già approvata: current/allowed combinati,
  falsy validi, allowed=[] nessuna riga, assenza richiesta errore, bypass esplicito.
- Verificare righe archiviate contro checkDuplicate e vincoli univoci reali.
- Preparare una piccola applicazione d'esempio con dichiarazione → rendering
  → letture relazionali → scritture → commit/rollback.
- Riscrivere il percorso didattico in inglese e verificare gli esempi; README,
  guida e reference devono distinguere capacità disponibili e future.

**Uscita V1:** scenario completo PostgreSQL, test di conformità del profilo V1,
nessuna divergenza silenziosa nota, build Sphinx rigorosa ed esempi eseguibili.
LT32–LT33 e verifica integrata F1–F4. Le policy applicative non sono partition
fisiche; queste ultime non vengono dichiarate completate.

## V2 — Espressività del modello e compiler

### F6 — Relazioni virtuali e formule avanzate

Leggere e fissare la nuova GEP come specifica, ricavandone i casi mancanti ai test
legacy. Implementare virtualRelation, formula-FK, joinColumn, aliasTable multi-hop
e compositeColumn; completare provider sql_formula/subquery, varianti/var_*,
pyColumn e bagItemColumn. Scegliere prima un ordine interno guidato dalle
dipendenze del resolver, senza introdurre un secondo motore di risoluzione.

**Uscita:** casi GEP tracciati, path attraverso virtuali, alias profondi e valori
calcolati verificati su dati reali; cicli e dipendenze non risolvibili diagnosticati.
LT07–LT08, LT17–LT19. Le PK composite esistenti non bastano per compositeColumn.

### F7 — Subtables, raccolte e macro

Implementare condizioni/parametri delle subtables, negazione e combinazioni,
context_subtables e indicatori derivati. Aggiungere raccolte correlate con forma,
ordine e cardinalità espliciti; completare le query many lasciate fuori da F3.
Introdurre un sistema di estensioni del compiler con sintassi macro compatibile
`#NOME`, nucleo comune ed estensioni applicative/dialect, partendo da quelle
richieste dai casi del corpus. Come concordato il 30 settembre 2026, questi
costrutti vengono elaborati durante la compilazione mediante operazioni
strutturate: SQL, parametri, riferimenti e trasformazioni del risultato da
eseguire dopo la lettura, secondo il contratto di ciascun costrutto.

**Uscita V2:** due raccolte indipendenti senza prodotto cartesiano o aggregateRows;
subtable combinate con policy; macro con binding corretto e diagnostica per
capacità assente. Confronti PG su risultati, NULL e raccolte vuote. LT10,
LT14–LT16, LT19–LT21.

## V3 — Interoperabilità e servizi applicativi

### F8 — Selection, Bag e lifecycle esteso

Consegnare Selection e output dati, poi il ponte per output UI e resolver
one/many con serializzazione. Aggiungere record cluster, cascata applicativa,
contatori/gerarchie; completare required_columns e consumo dei metadati UI.
Prevedere eventi/listener e cifratura/masking come incrementi distinti con prove
specifiche: non dedurre supporto reale dai soli mock del legacy.

**Uscita:** navigazione e scritture correlate atomiche, Bag tipizzate e output
confrontabili; gerarchie corrette fin dal primo inserimento. LT23–LT25,
LT28–LT31, LT34–LT35. Nessuna promessa di Bag condivisibili fra thread.

### F9 — Importatori e contratto con sqlmigration

Completare DB → modello per il profilo strutturale supportato; importare un
package legacy reale tramite adattamento dichiarativo, con diagnosi delle parti
non traducibili. Preservare nomi fisici, prefissi, chiavi e metadati recuperabili.
Coordinare i descriptor con sqlmigration e provarne ordinamento delle operazioni,
idempotenza e protezione dei dati nelle conversioni. Lavorare sul migratore è
un'attività distinta da certificare, non una proprietà ereditata da questo audit.

**Uscita V3:** DB importato senza diff residuo nel profilo supportato; package
importato utilizzabile per query/scritture/UI; oggetti non supportati segnalati;
secondo diff vuoto dopo apply e casi di conversione con dati verificati.
LT01–LT03, LT36–LT41.

## V4 — Capacità strutturali e backend ulteriori

### F10 — Incrementi indipendenti con accettazione propria

1. View, funzioni e trigger nativi: dichiarazione, importazione, dipendenze,
   versionamento/diff e coesistenza con gli hook Python.
2. Partition fisiche PostgreSQL: chiavi/vincoli, routing, attach/detach e
   lifecycle nel migratore; studio separato dalle subtables e dalla policy row.
3. Store/tenant: environment, nomi, isolamento e confini transazionali.
4. SQLite, richiesto dall'utente: adapter dati e driver, configurazione per file
   e memoria, letture/scritture e transazioni verificate sul backend reale.
   Collegare e verificare il percorso strutturale con l'adapter SQLite già
   presente in sqlmigration (che dispone anche di PostgreSQL, MySQL e SQL Server).
   Non reimplementare gli adapter di migrazione. Definire
   mapping degli schemi logici, tipi, foreign key, locking e limiti delle
   modifiche strutturali senza assumere equivalenza con PostgreSQL.
5. Ulteriori dialect dati: matrice di capacità e suite comune; struttura gestita
   tramite gli adapter di sqlmigration.

**Uscita per incremento:** roundtrip e migrazione verificati, letture/scritture
ove applicabili, limiti pubblici espliciti. L'async si valuta solo dopo il nucleo
sincrono, sulla base delle misure e del modello di isolamento degli oggetti.

## Controlli trasversali e chiusura delle fasi

- Ogni fase chiude con test pertinenti, integrazione reale dove necessaria,
  documentazione aggiornata e registro LT aggiornato. Non richiedere SQL
  testualmente identico quando dati ed effetti sono equivalenti.
- Misurare regressioni di numero query, compilazione e memoria; evitare N+1
  introdotti dai resolver. Ottimizzare solo con prove prima/dopo e cache con
  invalidazione corretta rispetto a modello, dialect ed environment (LT42).
- In caso di differenza non concordata, preparare il confronto concreto e
  sottoporlo all'utente; proseguire il lavoro indipendente. Non usare tale
  passaggio per richiedere nuovamente decisioni già prese.
- Conservare il lavoro di documentazione già presente; non mescolarlo
  accidentalmente alle modifiche runtime. Commit/push non sono autorizzati
  dalla sola richiesta di questo piano.

## Primo passo eseguibile

F0, con tre famiglie iniziali: rollback dopo errore SQL; lookup e compilazione
di `@customer_id.state`; alias/pkey e forma della riga restituita. Dopo averne
registrato il confronto, iniziare F1 e F2. Non partire da una riscrittura totale
né dall'aggiunta di nuove funzionalità prima di fissare questi contratti.
