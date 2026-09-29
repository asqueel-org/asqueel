# 03 — Finding: runtime, scritture, migrazioni e oggetti nativi

Fonti e grado di verifica: [registro](00-sources-and-evidence.md).

## F-R01 — Il lavoro attuale non consegna ancora un runtime di query e scrittura

**Evidenza:** COD, S01 superficie del package e renderer SQL placeholder.
Il percorso operativo è dichiarazione/validazione/proiezione migration, non ORM completo.
**Conseguenza:** il piano deve aggiungere esecuzione e DML; le precedenti suite
verificano il package corrente, non il prodotto prospettico.
**Verifica:** primo percorso PostgreSQL con SELECT, INSERT/UPDATE/DELETE e rollback.

## F-R02 — Il legacy ha contratti applicativi oltre il SQL

**Evidenza:** COD, S02 modello/table/runtime: hook, record, resolver e contesto;
S08 richiede conservare le parti utili in lettura e scrittura.
**Conseguenza:** distinguere primitive SQL da operazioni di dominio. Importare
uno schema o compilare una SELECT non dimostra che un'applicazione funzioni.
**Verifica:** applicazione campione, inventario dei percorsi CRUD/hook realmente usati.

## F-R03 — Portabilità di dialetto non significa equivalenza di driver

**Evidenza:** COD, S02 adapter: differenti placeholder, liste/tuple, empty IN,
regex, booleani, lock e trasformatori full-text; anche i driver PostgreSQL differiscono.
**Conseguenza:** capability per server/versione/driver/estensioni; limiti espliciti.
**Verifica:** matrice reale del sottoinsieme dichiarato, non solo coinstallazione.

## F-R04 — Policy di lettura non definiscono da sole le scritture

**Evidenza:** COD/INF, S02 filtri di query, subtable e partizioni logiche.
Un WHERE non assegna automaticamente discriminatore, tenant o campo di appartenenza.
**Conseguenza:** dichiarare regole INSERT, UPDATE che cambia appartenenza,
DELETE filtrato, bypass e vincoli del runtime.
**Verifica:** SP08/SP09, rollback ed eventuali hook importati.

## F-R05 — Streaming, pooling e async sono contratti operativi

**Evidenza:** INF, dipendenze fra cursori, connessioni, transazioni e contesto.
**Conseguenza:** chiusura su eccezione/cancellazione, limiti del pool, reset del
contesto e durata transazionale devono essere progettati. Async non accelera
automaticamente una singola query.
**Verifica:** test di risorse/concorrenza e memoria, separati dai test del compiler.

## F-R06 — Bulk e scritture per record non sono intercambiabili

**Evidenza:** S09 COPY/INSERT e INF sui callback Python.
**Conseguenza:** batch, COPY e SQL diretto devono dichiarare quali validazioni
e hook attraversano. Nessun salto silenzioso degli hook in nome delle prestazioni.
**Verifica:** risultati/effetti confrontati con il canale di dominio; [COPY](https://www.postgresql.org/docs/18/sql-copy.html).

## F-R07 — Hook Python e trigger nativi hanno confini di esecuzione diversi

**Evidenza:** S09 trigger e S08 prospettiva richiesta.
I trigger operano nel DB anche fuori dal percorso Python; row/statement e
deferrabilità non si riducono a un unico callback per record.
**Conseguenza:** responsabilità delle regole, ordine delle fasi e gestione degli
effetti devono evitare duplicazione. Progettare anche le notifiche dopo commit.
**Verifica:** DB03 con rollback e bulk; [trigger](https://www.postgresql.org/docs/18/trigger-definition.html).

## F-R08 — Caching richiede dipendenze esplicite

**Evidenza:** COD/INF, S02 varianti, env, tenant, store, locale e policy.
**Conseguenza:** distinguere cache di parsing, piano e risultati; invalidare per
versione modello/profilo/dialetto e dipendenze strutturali. Non condividere valori sensibili.
**Verifica:** due contesti simultanei, aggiornamento modello e variazione di una formula.

## F-R09 — Ottimizzare richiede un carico rappresentativo

**Evidenza:** INF, nessun benchmark del nuovo runtime eseguito.
**Conseguenza:** prima eliminare molteplicità inutili e N+1 reali, poi confrontare
strategie; misurare compilazione, DB, trasferimento e postprocessing separatamente.
**Verifica:** mediana/p95, memoria, query count, righe e buffer su distribuzioni diverse.
EXPLAIN ANALYZE esegue il comando: [riferimento](https://www.postgresql.org/docs/18/using-explain.html).

## F-R10 — L'identità pubblica dei risultati non deve dipendere dal piano fisico

**Evidenza:** INF da alias, meta UI e prefissi del modello.
**Conseguenza:** cambiare join o nome fisico non deve cambiare arbitrariamente
le chiavi della risposta. Tipo, provenienza e profilo UI accompagnano il risultato.
**Verifica:** stesso QuerySpec con strategie SQL alternative e mapping fisico diverso.

## F-G01 — Reader, emitter e proiezione migration esistono già

**Evidenza:** COD/PRE, S01 reader/emitter/migration e rapporto delle suite.
**Conseguenza:** usarli come base del percorso di import/export; non riscriverli
senza verificare quali contratti sono riutilizzabili.
**Limite:** questo non prova importazione di ogni oggetto PostgreSQL o modello legacy.
**Verifica:** round-trip del sottoinsieme supportato e rapporto degli oggetti esclusi.

## F-G02 — Il renderer DDL diretto è un placeholder

**Evidenza:** COD, S01 renderer.py: SqlRenderer con mode sql e nessuna implementazione DDL.
**Conseguenza:** la proiezione migration è il percorso corrente; non presentare
il nome renderer_sql come prova di generazione SQL completa.
**Verifica:** mantenere esplicite le capability e scegliere il confine col migratore.

## F-G03 — Nomi degli indici e ordinamento DESC hanno difetti riprodotti

**Evidenza:** PRE/DIS, S05, [issue #8](https://github.com/genropy/genro-sqlmigration/issues/8):
nome fisico esplicito perso a favore del nome generato; lettura PostgreSQL DESC
con indicizzazione errata di indoption nel caso riprodotto.
**Conseguenza:** round-trip e diff degli indici non certificati per quei casi.
**Verifica:** riprodurre sulle nuove versioni, correggere upstream e rimuovere gli xfail appropriati.

## F-G04 — Quoting degli identificatori non è completo

**Evidenza:** PRE/DIS, S05, [issue #9](https://github.com/genropy/genro-sqlmigration/issues/9):
quote_identifier assente e nomi di indice non gestiti uniformemente dai writer.
**Conseguenza:** nomi riservati, caratteri speciali e quote richiedono un contratto
centrale; prefissi e nomi importati rendono il caso parte del progetto, non marginale.
**Verifica:** test per dialect su nomi espliciti e caratteri di quoting.

## F-G05 — Gli xfail attestano difetti noti, non correzioni

**Evidenza:** PRE, S01/S05: strict xfail limitati a SHA e specifiche eccezioni;
122 passati e 2 xfail nel precedente ambiente PostgreSQL.
**Conseguenza:** non trasformare «suite verde con xfail» in «migratore corretto».
**Verifica:** nuova dipendenza stabile pertinente, riproduzione e passaggio senza
eccezioni attese. Nessun nuovo test runtime è stato eseguito per questo dossier.

## F-G06 — Il contratto attuale esaminato non rappresenta tutta la prospettiva nativa

**Evidenza:** COD, S04 structures/validation: root schemas/extensions/event_triggers;
contenitori tabella columns/relations/constraints/indexes.
**Conseguenza:** view, funzioni, trigger DML e storage partitioning richiedono
estensione versionata e consumer coerenti, non soltanto attributi extra arbitrari.
**Verifica:** reader → struttura → diff → writer → nuova introspezione.

## F-G07 — Event trigger presente nella struttura non significa supporto operativo

**Evidenza:** COD, S04 command_builder.added_event_trigger e removed_event_trigger
sono no-op. Event trigger DDL e trigger DML sulle tabelle sono famiglie diverse.
**Conseguenza:** dichiarare capability incompleta, senza successo silenzioso
di una migrazione che promette di gestire l'oggetto.
**Verifica:** DB04 e prove con oggetti realmente presenti/assenti nel database.

## F-G08 — Gli oggetti nativi richiedono identità e dipendenze proprie

**Evidenza:** S08/S09: funzioni sovraccaricate, view e trigger riferiscono altri oggetti.
**Conseguenza:** firma della funzione nell'identità, tipo di ritorno e proprietà;
grafo delle dipendenze, SQL/corpo preservato, replace o ricreazione secondo il caso.
SQL dinamico può richiedere dipendenze dichiarate dal modello.
**Verifica:** DB01/DB02/DB05; [funzioni](https://www.postgresql.org/docs/18/sql-createfunction.html),
[view](https://www.postgresql.org/docs/18/sql-createview.html).

## F-G09 — Partizionamento fisico è una migrazione strutturale e dei dati

**Evidenza:** S09; differente da F-M17.
**Conseguenza:** strategia, chiavi, bounds, default partition, attach/detach,
indici/vincoli e trasformazione di tabelle esistenti richiedono un piano specifico.
**Verifica:** DB06, dati ai limiti e conservazione dei dati; [partizioni](https://www.postgresql.org/docs/18/ddl-partitioning.html).

## F-G10 — Oggetti non gestiti non possono diventare rimozioni implicite

**Evidenza:** INF da perimetro incompleto dell'introspezione e dipendenze native.
**Conseguenza:** il diff deve distinguere assente, sconosciuto ed esterno al
perimetro. Non interpretare una lettura parziale come desiderio di cancellazione.
**Verifica:** DB con oggetti esterni e introspezione limitata; nessun DROP/CASCADE
automatico per coprire un limite del modello.
