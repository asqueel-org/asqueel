# 08 — Adapter dati per dialetto: responsabilità e piano di estrazione

29 settembre 2026. Piano richiesto dopo la prima implementazione V1.
Questo documento conserva il piano del refactoring. Dopo l'autorizzazione
«procedi», l'[implementazione e le verifiche](../data-adapters-delivery.md)
ne documentano l'esecuzione. L'obiettivo è estrarre PostgreSQL senza cambiare
la semantica verificata. Gli altri dialetti arrivano successivamente.

## 1. Confine dei componenti

| Componente | Decide e produce | Non deve fare |
|---|---|---|
| Modello risolto | Identità, nomi logici/fisici, tipi logici, relazioni, formule e metadati UI. | Scegliere placeholder del driver o generare query. |
| Compiler comune | Risoluzione dei riferimenti, join richiesti, cardinalità, scope, alias, dipendenze delle formule e descrizione dei risultati. | Incorporare peculiarità PostgreSQL nella semantica Genro. |
| Adapter dati del dialetto | Sintassi SQL per letture/scritture e traduzione delle operazioni logiche supportate. | Aprire connessioni, ricostruire il modello, inventare join o applicare hook. |
| Driver | Binding concreto, adattamento dei valori, connessioni, cursori, primitive transazionali, risultati ed errori del client DB. | Risolvere relazioni o tradurre sintassi Genro. |
| Runtime | Proprietà della sessione, ordine delle operazioni, esecuzione sincrona sul thread chiamante e pulizia. | Comporre SQL di SELECT/DML o duplicare il driver. |
| Adapter strutturali di sqlmigration | Introspezione, rappresentazione fisica, confronto, DDL e operazioni strutturali. | Diventare dipendenza obbligatoria per leggere e scrivere dati. |

Il flusso proposto è:

```text
richiesta Genro + modello
        → compiler comune → piano risolto
        → adapter del dialetto → statement con parametri strutturati
        → preparazione del driver → SQL e valori eseguibili
        → runtime/sessione → esecuzione del driver → risultato
```

La preparazione dei parametri non effettua I/O. Il runtime controlla quando e
dove le primitive del driver vengono eseguite. Un futuro driver async nativo
riuserà compiler e adapter dati, con un percorso di esecuzione adatto; non sarà
necessario simulare un driver sincrono né duplicare la semantica delle query.

## 2. Compiti degli adapter dati

### AD-01 — Identificatori e nomi qualificati

Quotare identificatori e comporre schema/tabella/colonna/alias già risolti dal
modello. Non dedurre package dal nome fisico o applicare una seconda volta il
prefisso. Gestire caratteri speciali, parole riservate, Unicode e limiti del
backend. Un nome troppo lungo deve avere una politica esplicita: nessun
troncamento silenzioso che possa produrre collisioni.

Il quoting SQL è distinto dall'escaping del protocollo dei parametri: `%`
fa parte del nome SQL; `%%` è un'esigenza del formatter psycopg corrente.

### AD-02 — SELECT e clausole

Rendere proiezioni, FROM, join già pianificati, predicati, ordinamento e
paginazione. Preservare ordine, NULL e cardinalità decisi dal piano.
LIMIT/OFFSET appartengono alla sintassi del dialetto; scelta della paginazione
keyset e costruzione del suo predicato appartengono al livello comune.

GROUP BY, HAVING, CTE, window e LATERAL diventano operazioni dichiarate quando
il compiler le supporta: estrarre l'adapter non autorizza a dichiararle già
implementate nella V1.

### AD-03 — INSERT, UPDATE e DELETE

Tradurre destinazione, colonne fisiche, valori associati a parametri,
predicati, DEFAULT VALUES e risultati richiesti. Conservare la protezione
contro UPDATE/DELETE privi di predicato esplicito.

La validazione delle colonne scrivibili è comune; la forma SQL è del dialetto.
UPDATE con join, insert multiplo, upsert e merge saranno capacità separate,
non varianti implicitamente disponibili perché esiste una funzione `update`.

### AD-04 — Valori generati e RETURNING

Descrivere il supporto a RETURNING per ciascuna operazione, colonne/espressioni
ammesse e forma del risultato. Non sostituire silenziosamente RETURNING con
una SELECT separata: concorrenza, trigger, atomicità e costo potrebbero cambiare.
Un eventuale recupero alternativo delle chiavi deve avere un contratto specifico
e verifiche reali sul backend.

### AD-05 — Espressioni, funzioni e tipi SQL

Tradurre le operazioni logiche esplicitamente rappresentate: cast, confronti,
operatori, funzioni, date, JSON e altre famiglie introdotte progressivamente.
Conoscere il tipo SQL utilizzabile in un'espressione; lasciare i tipi DDL al
contratto strutturale e l'adattamento degli oggetti Python al driver.

Le espressioni SQL raw restano una via applicativa specifica del dialetto.
Non vengono riscritte con sostituzioni testuali fingendo portabilità. La V1
deve conservare stringhe, commenti, dollar quote e cast PostgreSQL; le regole
lessicali specifiche devono essere fornite dal profilo del dialetto, mentre
la risoluzione di `$campo` e `@relazione.campo` resta comune.

### AD-06 — Lock e caratteristiche transazionali SQL

Rendere future clausole di locking e dichiararne il supporto, per esempio
le varianti di FOR UPDATE. La sessione decide il confine transazionale;
il driver espone begin/commit/rollback e, quando supportate, le operazioni
necessarie per isolamento e savepoint. L'adapter può fornire sintassi richiesta
dal backend, ma non apre o chiude autonomamente la transazione.

### AD-07 — Capacità e diagnostica

Esporre capacità granulari, associate al profilo di backend/versione quando
necessario: SELECT, DML, RETURNING per operazione, locking, tipi, funzioni e
limiti. Distinguere capacità sintattiche del dialetto da capacità del driver
e dal sottoinsieme effettivamente implementato nel compiler.

Un'operazione non supportata deve fallire prima dell'esecuzione quando la
limitazione è nota. Il compiler offline usa un profilo esplicito; non apre
connessioni per scoprirlo. Il runtime verifica la compatibilità del profilo
con il server e il driver selezionati senza dichiarare capacità ignote.

## 3. Compiti del driver e del runtime

### DR-01 — Preparazione dei binding

Ricevere frammenti SQL e riferimenti a parametri distinguibili strutturalmente.
Produrre il paramstyle richiesto dal client, gestendo ripetizioni, ordine e
parametri assenti. Non convertire placeholder con regex sul testo finale:
stringhe, commenti, identificatori e operatori possono contenere gli stessi simboli.

Per psycopg: placeholder nominati e raddoppio dei soli `%` letterali al confine
di preparazione, una volta sola. Questo comprende i nomi quotati. Gli adattamenti
di date, Decimal, byte, JSON e altri oggetti Python devono essere espliciti e
collaudati; nessuna conversione globale a stringa.

### DR-02 — Client DB e risultati

Isolare import opzionale del client, apertura/chiusura, cursori, execute,
fetch e rowcount. Restituire nomi e valori senza perdere NULL o duplicati.
I metadati logici restano quelli del compiler; informazioni supplementari
del driver non devono alterare identità e UI della colonna.

Classificare solo errori riconoscibili e conservare causa originale, SQLSTATE
o equivalenti disponibili. Non esporre automaticamente valori sensibili nei
messaggi. Retry e recupero dagli errori non sono compiti impliciti dell'adapter.

### DR-03 — Primitive e proprietà della connessione

Fornire commit, rollback e chiusura, senza possedere il ciclo di vita della
transazione applicativa. La V1 usa il thread chiamante, una connessione nuova
per transazione e risultati materializzati.

Il runtime mantiene rollback-only, rifiuto delle transazioni annidate non
supportate, proprietà del thread e chiusura prima del rilascio. Un errore durante commit può lasciare esito sconosciuto;
nessun adapter deve trasformarlo in rollback certo o retry automatico.

## 4. Rapporto con sqlmigration e importazione

Il resolver possiede il mapping logico/fisico. Adapter dati e proiezione
strutturale ricevono gli stessi nomi risolti. Per quoting e tipi si definiscono
contratti ed esempi condivisi, senza far dipendere il runtime dati da
sqlmigration né introdurre dipendenze circolari fra i package.

Nel primo intervento si confrontano le implementazioni con test comuni;
un eventuale piccolo package condiviso si valuterà soltanto dopo aver
identificato una duplicazione stabile. L'escaping dei placeholder del driver
non deve finire nel quoting DDL del migratore.

`inspect_postgres` attuale interroga direttamente i cataloghi per conservare
informazioni aggiuntive e segnalare perdite. Questa è una responsabilità
**strutturale**, non del futuro adapter dati. L'estrazione deve inventariarne
le differenze rispetto al reader sqlmigration e definire un provider di
catalogo, mantenendo la facciata di import esistente. La convergenza del reader
può essere un intervento successivo coordinato sul migratore: non si eliminano
i controlli su collation, sequenze, FK e indici per riutilizzare meno metadati.

La disponibilità di un adapter dati non certifica quella di un migratore
equivalente e viceversa. La matrice pubblica deve distinguere le due coperture.

## 5. Estrazione concreta dal codice V1

| Codice attuale | Destinazione proposta | Vincolo |
|---|---|---|
| `compiler.py`: `_Context.field`, `related`, formule, alias e metadati | Resolver/compiler comune | Una sola risoluzione delle relazioni, indipendente dal backend. |
| `compiler.py`: scanner e riconoscimento dei riferimenti | Scanner comune con regole lessicali del dialetto | Non perdere protezione di stringhe/commenti/cast e nomi quotati. |
| `compiler.py`: `select`, DML e composizione SQL | Piano comune + adapter dati PostgreSQL | Conservare wildcard, predicati, binding e RETURNING della V1. |
| `compiler.py`: quoting e `%` | Quoting nell'adapter; `%` nel formatter del driver | Eliminare l'attuale accoppiamento SQL/psycopg senza doppio escaping. |
| `runtime.py`: `_open`, `_execute`, `_finish` | Primitive del driver psycopg invocate dal runtime | Thread, ordine e cleanup invariati; il runtime conserva lo stato transazionale. |
| `runtime.py`: proprietà del thread, lifecycle | Runtime comune sincrono per driver iniettati | Nessuna duplicazione per ogni dialetto. |
| `importers.py`, `projection.py` | Confine strutturale/provider, separato dall'adapter dati | Warning e rifiuti di proiezioni non fedeli preservati. |

Nomi di moduli proposti: `dialects/base.py`, `dialects/postgres.py`,
`drivers/base.py`, `drivers/psycopg.py`, `query_plan.py`. Sono assegnazioni
preliminari, non API pubbliche già introdotte.

Il piano intermedio deve essere minimo: SELECT/INSERT/UPDATE/DELETE, riferimenti
fisici risolti, join, proiezioni, predicati, ordinamento, limiti, parametri e
metadati. Sono ammessi frammenti SQL opachi con provenienza/dialetto espliciti;
non serve un AST completo di PostgreSQL per estrarre il confine.

Le facciate pubbliche `PostgresCompiler` e `PostgresDatabase` restano disponibili
e delegano ai componenti estratti. Il contratto pubblico V1 di `CompiledQuery`
e dell'esecuzione manuale psycopg rimane valido durante la transizione.
I nuovi statement interni precedono la preparazione del driver; non si cambia
in silenzio il significato di `CompiledQuery.sql`. Eventuali formati nuovi
devono distinguere profilo di dialetto e binding e rifiutare abbinamenti errati.

## 6. Fasi e compiti degli agenti

Le fasi seguenti descrivono l'ordine concordato; lo stato verificato è nel
rapporto di implementazione collegato sopra. Il numero degli agenti operativi
resta tre, con un integratore; si lavora in parallelo dopo il primo gate.

| Fase | Attività e assegnazione | Risultato e gate |
|---|---|---|
| A0 — Contratti | Integratore: piano minimo, statement/binding, protocolli dialetto/driver, facciate e matrice delle capacità. Agenti: review dei contratti e inventario delle dipendenze. | Firme concordate e esempi completi per SELECT/CRUD; nessun secondo resolver. |
| A1 — Estrazione parallela | Agente A: compiler comune, piano e riferimenti. Agente B: adapter PostgreSQL, rendering e quoting. Agente C: driver psycopg e runtime sincrono. | Ogni componente passa test propri contro gli stessi contratti; file condivisi modificati solo dall'integratore. |
| A2 — Integrazione | Integratore collega le facciate. A/B verificano metadati e SQL; C verifica transazioni e risorse. | Suite V1 e demo passano; SQL/risultati restano equivalenti, nessuna regressione di cancellazione. |
| A3 — Confine strutturale | A inventaria il catalog provider e i tipi; B confronta naming/quoting dati-DDL; C verifica installazione senza sqlmigration. | Nessuna dipendenza inversa e nessuna perdita nei gate di import/proiezione. Il trasferimento di codice fra repo, se necessario, diventa un lavoro separato. |
| A4 — Consegna | Revisione incrociata, documentazione capacità e test del wheel. | PostgreSQL è un'implementazione dell'interfaccia; nessun altro dialetto è dichiarato supportato. |

**Proprietà dei file:** A gestisce compiler/piano e relativi test; B gestisce
`dialects/` e relativi test; C gestisce `drivers/`, runtime e relativi test.
L'integratore possiede contratti comuni, export pubblici, dipendenze, CI e
test end-to-end. La separazione iniziale di `compiler.py` è coordinata prima
delle modifiche parallele, perché oggi contiene sia resolver sia emitter SQL.

L'agente del dialetto non modifica da solo il piano; quello del runtime non
modifica il formato dei binding; quello del compiler non introduce direttamente
SQL specifico per risolvere una differenza di backend.

## 7. Verifiche obbligatorie

1. Preservare i 202 test della baseline V1 documentata, distinguendo unitari e
   PostgreSQL reali; aggiungere test dei nuovi confini, non solo delle facciate.
2. Compilare senza connessione, psycopg o sqlmigration installati; importare il
   package core senza risolvere dipendenze opzionali.
3. Provare parametri ripetuti, collisioni fra binding DML/predicati, NULL, apici,
   percentuali, nomi Unicode, commenti, dollar quote e cast; niente doppio escaping.
4. Verificare naming identico fra dati e proiezione strutturale: schema, prefisso,
   override, colonna quotata e identità dei metadati anche attraverso alias.
5. Provare una capacità disabilitata con un adapter di test: errore esplicito,
   nessuna esecuzione o emulazione silenziosa. Un fake non certifica un dialetto.
6. Verificare CRUD/RETURNING, transazioni concorrenti isolate, rollback dopo errore,
   saturazione, cancellazione ripetuta, commit incerto e chiusura su PostgreSQL.
7. Conservare i test di idempotenza e i rifiuti di proiezioni con perdita
   semantica; leggere dati da un modello con warning non autorizza migrazioni.
8. Verificare che il runtime non importi il compiler PostgreSQL per eseguire
   statement e che il compiler comune non dipenda da psycopg.
9. Controllare il costo della separazione: niente connessioni durante compile,
   niente round-trip aggiuntivi per una normale operazione, nessun nuovo
   passaggio dei valori attraverso interpolazione testuale.

## 8. Versioni successive

Questo intervento completa la separazione architetturale della V1, prima di
ampliare la semantica V2. Non aggiunge compatibilità legacy né un nuovo dialetto.
Le virtualRelation e gli aggregati futuri devono entrare nel piano comune e
delegare solo la resa SQL specifica agli adapter.

Il secondo dialetto si sceglierà su un'applicazione concreta: prima subset e
capability, poi driver e test su database reale. Un eventuale driver PostgreSQL
async nativo è un asse indipendente dal secondo dialetto. COPY, bulk, streaming,
upsert e locking avanzato richiederanno contratti separati, evitando metodi
generici che nascondano differenze di atomicità o comportamento.
