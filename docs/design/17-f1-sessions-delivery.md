# 17 — F1: sessioni, connessioni nominate ed environment

**Aggiornamento:** rapporto del nucleo precedente; F1 resta aperta. La bozza
successiva di trigger/deferred è esaminata nel [riesame 18](18-interrupted-lifecycle-review.md);
le correzioni sono nella [consegna 19](19-deferred-lifecycle-fixes.md).

30 settembre 2026. Implementazione locale successiva a `2bed211`, senza commit
né push. Riferimenti: [piano operativo](15-operational-plan.md),
[confine DB/app](16-legacy-db-application-boundary.md).

## Perimetro e stato

Consegnato il nucleo F1: transazione implicita, recupero dopo errore SQL,
connessioni nominate persistenti e ambiente applicativo mutabile. Non è la
chiusura del censimento completo F0 né della compatibilità legacy nel suo insieme.

La localizzazione completa, comprese validazione Babel del locale e specificità
Windows, rimane un punto aperto APP04. Il nuovo fallback locale usa GNR_LOCALE,
il locale di sistema e infine en_GB; il valore esplicito è conservato. Questa
limitazione è dichiarata, non registrata come differenza approvata dall'utente.

## Contratti implementati

| Contratto | Risultato |
|---|---|
| Transazione implicita | La prima istruzione avvia il lavoro; commit/rollback espliciti, nessun obbligo di db.transaction(). |
| Errore durante esecuzione SQL | Rollback immediato sulla connessione selezionata e propagazione dell'errore originale; la sessione è riutilizzabile. |
| Errore nel rollback automatico | Connessione scartata, outcome unknown, errore originale preservato con causa; recupero esplicito prima di nuove operazioni. |
| Connessioni nominate | currentConnectionName/tempEnv(connectionName=...), default _main_connection, apertura lazy e stato separato. |
| Riuso fisico | Commit/rollback non chiudono la connessione; verificato anche confrontando pg_backend_pid(). |
| Indipendenza | Commit, rollback ed errore SQL di B non concludono il lavoro pendente di A. |
| Chiusura | closeConnection() annulla/chiude tutti i nomi e permette riapertura; close() chiude definitivamente il DB. Tentata pulizia di tutti i nomi anche se uno fallisce. |
| Ambiente | currentEnv è dict mutabile, assegnabile e sostituibile; updateEnv/clearCurrentEnv; None distinto da rimozione, 0/False preservati. |
| tempEnv | Ripristina chiavi preesistenti; rimuove chiavi nuove ancora uguali al temporaneo; conserva nuove chiavi cambiate e modifiche estranee allo scope. Yield del db applicativo. |
| Snapshot | current_env è una copia separata; le snapshot per compilazione risolvono workdate/locale. |
| Guardie | Thread proprietario, ambiente della query compilata e profilo del driver verificati prima dell'esecuzione. |
| Store | Nomi store non supportati sono rifiutati esplicitamente: non vengono instradati per errore sul DB principale. |

Il contesto applicativo usa ApplicationEnvironment; lo SqlEnvironment autonomo
mantiene le proprie scope copiate/context-local per il compiler/runtime di basso
livello. Iniezione di SqlEnvironment conserva la condivisione della variabile di
contesto sottostante. La vista mutabile dell'applicazione è sincrona, non una
promessa di isolamento fra task async o di condivisione thread-safe della Bag.

## Differenze ancora visibili e confini

- Gli errori Python negli hook mantengono il preesistente stato rollback-only.
  Non si deduce un rollback automatico di ogni eccezione Python dalla sola
  implementazione legacy di execute. La pipeline completa è F4/F8.
- L'eventuale db.transaction() resta un'estensione opzionale: possiede il nome
  selezionato all'ingresso e non può riuscire silenziosamente dopo un errore
  SQL catturato all'interno. Gli altri nomi rimangono indipendenti.
- Le code deferToCommit/deferAfterCommit, deferredRaise, gli eventi applicativi,
  autoCommit e gli override GnrSqlAppDb non sono implementati da questa fase.
  Il loro nucleo deve essere completato per connessione prima di F2, senza copiarne
  eventuali perdite di isolamento non ancora chiarite nel legacy.
- Non vengono introdotti store/tenant, async o nuovi comportamenti del compiler
  per path/query/record. Il runtime di basso livello conserva la transazione
  distinta per singolo execute e il proprio context manager.
- Se un commit ha esito unknown, non si assume che la scrittura sia fallita:
  l'app deve riconciliare lo stato prima di ripeterla.

## Prove e attribuzione

1. Baseline mirata prima delle modifiche: 69 test superati.
2. Quattro nuovi contratti inizialmente fallenti: nomi indipendenti, rollback SQL,
   ambiente mutabile/tempEnv e rifiuto degli store non supportati.
3. [Oracle legacy eseguibile](evidence/f1_legacy_oracle.py) e
   [risultati/hash sorgenti](evidence/f1_legacy_oracle.json): classi originali
   estratte via AST, con corpi dei metodi conservati, eseguite su PostgreSQL
   temporaneo in schema casuale eliminato a fine prova. Copre tempEnv,
   connessioni distinte, visibilità, rollback SQL e identità fisica dopo commit
   e rollback. Esclude framework, audit decorator e dispatcher deferred.
4. Nuovi test del prodotto: driver simulato per failure/reentrancy/cleanup e
   PostgreSQL reale per visibilità indipendente e rollback di scritture/hook
   dopo violazione di vincolo. Include recupero dopo fallimento del rollback,
   closeConnection/riapertura e snapshot workdate obsolete.
5. Suite finale: **532 passati, nessuno saltato** sul PostgreSQL temporaneo
   locale porta 55449, ruolo postgres. Una prima esecuzione mirata con ruolo
   gporcari aveva prodotto errori di setup perché il ruolo non esiste: corretta
   la configurazione del test, senza modificare codice per nasconderli.
6. Ruff sui file Python della fase: pass; mypy: pass su 31 file sorgente;
   Sphinx HTML con warning come errori: pass; git diff --check: pass.

I test del vecchio comportamento rollback-only su errori SQL sono aggiornati
al contratto legacy verificato. I test degli errori Python negli hook restano.
Il driver simulato ora svuota la propria lista transazionale dopo commit,
necessario perché la connessione viene riutilizzata invece di essere scartata.

## Documentazione e seguito

Quickstart e tutorial ora mostrano transazioni implicite e commit/rollback
espliciti. Guide environment/transazioni/limiti/compatibilità aggiornate. La
preview esistente riceve la nuova build Sphinx.

F1 ha evidenza eseguibile sul perimetro sopra; restano espliciti il punto APP04
e l'approfondimento delle eccezioni hook, senza dichiararli già compatibili.
F2 resta pianificata e attende la chiusura di F1, incluse le code pending.
La presenza di più sessioni non dimostra il completamento del lifecycle.
