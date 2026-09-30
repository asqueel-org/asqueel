# Audit runtime, sessione e lifecycle applicativo legacy / nuovo

Data: 29 settembre 2026. Questo documento confronta comportamenti osservabili nel sorgente; non certifica compatibilità applicativa legacy.

Riferimenti riproducibili:

- **L**: `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr`, commit `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
- **N**: radice di questo repository, HEAD `b023a9bb25f3135ad1a10fb17a485eac27cf4237`, che contiene già gli hook update/delete. I riferimenti di riga descrivono i sorgenti committati; questo audit non li modifica.
- **Prova sorgente** significa lettura dei percorsi indicati. **Prova PG** significa esercizio del nuovo sistema su PostgreSQL reale, non esecuzione differenziale del legacy.

## Conclusione

La nuova facciata applicativa ha recuperato il requisito essenziale del legacy: operazioni di più tabelle e loro hook possono partecipare alla stessa unità di lavoro senza commit impliciti. Ha inoltre introdotto uno snapshot bloccato per gli hook update/delete, errori espliciti di cardinalità e chiusura deterministica delle connessioni.

Rimane un nucleo per applicazioni nuove. I sei nomi `trigger_on*` non ricostruiscono da soli il lifecycle legacy: mancano protezioni, field trigger, trigger di package esterni, contatori, callback differite, propagazione delle relazioni, totalizzatori, notifica e trasformazioni dei valori dell'adapter. Copiare una classe legacy in `x_table_class` non equivale a importare il package né garantisce che quella classe funzioni.

## Matrice delle capacità

Le priorità indicano dove decidere il contratto: **V1** applicazioni nuove; **bridge** compatibilità selettiva; **futuro** funzionalità ulteriore. “Assente” riguarda il percorso applicativo esaminato, non l'impossibilità di implementarlo.

| Comportamento | Legacy, prova sorgente | Nuovo, prova sorgente | Gap / scelta / priorità |
|---|---|---|---|
| Identità database e tabelle | `L/sql/gnrsqltable/crud.py:116` delega a `self.db`; package e implementazione possono cambiare contesto | `N/src/asqueel/application.py:26`, `:65`: unico grafo risolto, handle tabella stabili, sessione condivisa | Base V1 presente; nessuna equivalenza con composizione di package legacy |
| Commit delle operazioni applicative | `L/sql/gnrsql/execute.py:46`: `autocommit=False`; CRUD delega senza commit | `N/src/asqueel/session.py:52`, `:91`: prima esecuzione apre transazione mantenuta fino al confine esplicito | Preservato il requisito di unità di lavoro, non ogni comportamento transazionale |
| API tecnica alternativa | Legacy execute restituisce cursore e consente `autocommit` | `N/src/asqueel/runtime.py:72`: `Database.execute` fa una transazione per chiamata; `application.py:91` usa invece Session | V1: documentare chiaramente questa differenza. Usare il runtime basso livello al posto della facciata spezza l'atomicità tra chiamate |
| Connessioni e thread | `L/sql/gnrsql/connections.py:77`: cache per thread e coppia store/connectionName | `N/src/asqueel/runtime.py:54`, `session.py:73`: proprietario thread fisso, connessione chiusa al completamento della transazione | Modernizzazione deliberata; nessuna condivisione di un database applicativo tra thread. Store/tenant rinviati |
| Commit differito / più store | `L/sql/gnrsql/transactions.py:47`, `:95`: code prima/dopo commit, pending exceptions, iterazione connessioni | `N/src/asqueel/session.py:91`: singola transazione, nessuna coda differita | Bridge: analizzare ogni callback; futuro: outbox/eventi. Non chiamare il legacy commit multi-connessione una transazione distribuita atomica |
| Errori e cleanup | `L/sql/gnrsql/connections.py:40` ignora errori di cleanup; execute dichiara rollback su errore | `N/src/asqueel/runtime.py:152`: tenta close anche dopo errore commit/rollback, preserva errore, outcome `unknown`; `session.py:47` impone rollback-only | V1 presente, semantica più esplicita. Hook con errore intercettato non autorizza commit |
| Confini manuali e context manager | Legacy usa principalmente commit/rollback e helper specifici | `N/src/asqueel/session.py:102`: no nested/adoption di transazione pendente; `application.py:96` vieta confini durante hook/write | Modernizzazione V1; niente savepoint o nested transaction implicite |
| Ambiente | `L/sql/gnrsql/env.py:59`: dizionario vivo per thread, setter e updateEnv | `N/src/asqueel/environment.py:34`, `:39`, `:58`: ContextVar per istanza, snapshot deepcopy, scope ripristinato | V1 deliberatamente incompatibile con `db.currentEnv[key] = value`; bridge richiede adattamento esplicito |
| Query e ambiente tardivo | `L/sql/gnrsql/execute.py:46`: sostituzione env in execute | `N/src/asqueel/application_table.py:105`: ricompilazione terminale; `runtime.py:63`: verifica environment binding | Query riutilizzabile cambia ambiente al fetch; CompiledQuery già prodotta può essere rifiutata in altro ambiente. V1 presente |
| Insert e input | `L/sql/gnrsql/write.py:134`: checkPkey, validazioni, field/table/package hooks, counters, dbo, adapter e notifiche | `N/src/asqueel/application_table.py:294`: copia input, prehook, compiler/execute, overlay RETURNING, posthook | Solo hook tabella. Generazione PK/valori di default Python e trasformazioni legacy non sono ricostruite |
| Update e snapshot | `L/sql/gnrsqltable/crud.py:116` accetta old_record del chiamante; `L/sql/gnrsql/write.py:223` lo inoltra | `N/src/asqueel/application_table.py:306`: con override acquisisce record fisico bloccato, fonde patch, consegna copie indipendenti di old_record | Modernizzazione V1. Non è un controllo optimistic locking contro lo snapshot letto prima dal chiamante |
| Lock degli hook | Il normale update CRUD non introduce da solo SELECT FOR UPDATE; delete con PK stringa lo fa (`L/sql/gnrsqltable/crud.py:101`) | `N/src/asqueel/application_table.py:274`: SELECT colonne fisiche, `for_update=True`, limite 2, senza filtri draft/deleted, partizione mantenuta | Nuovo contratto più forte e uniforme soltanto nel ramo con hook. Può bloccare fino a due righe prima di rifiutare una selezione multipla |
| Identificazione update | `L/sql/adapters/_gnrbaseadapter.py:843`: prepara record e seleziona pkey/old_record | `N/src/asqueel/application_table.py:319`: salva predicato PK prima del prehook, UPDATE sul vecchio identificativo | V1: cambio PK possibile senza perdere la riga; PK composta e zero collaudati. Nessuna propagazione Python alle righe correlate |
| Delete e mutazione hook | `L/sql/gnrsql/write.py:268`: protezioni, cascade, hook e counters | `N/src/asqueel/application_table.py:332`: snapshot bloccato, chiave salvata prima del prehook, stesso record pre/post | V1: mutazioni del prehook visibili al posthook, non cambiano il bersaglio DELETE; protezioni/cascade applicative assenti |
| Cardinalità e operazioni batch | Legacy record può ignorare missing/duplicate (`L/sql/gnrsqldata/record.py:319`); CRUD ha helper batch dedicati | `N/src/asqueel/application_table.py:143`, `:274`: esattamente una riga per hook; senza override update/delete mantengono SQL batch | Scelta V1 esplicita: aggiungere un hook modifica anche la cardinalità ammessa dall'operazione |
| Soft delete / restore | Logical deletion partecipa al modello e al caricamento record legacy (`L/sql/gnrsqldata/record.py:356`) | `N/src/asqueel/application_table.py:353`: delega a update; con hook usa snapshot anche della riga già cancellata | V1 collaudato. Non simula automaticamente tutti i trigger o tutte le convenzioni legacy |
| Formule e dati scrivibili | `L/sql/adapters/_gnrbaseadapter.py:728`: elimina virtuali e relazioni dal record, serializza Bag, applica cifratura e sql_value | `N/src/asqueel/compiler.py:477`: colonne sconosciute/formula rifiutate; snapshot hook include solo colonne fisiche | V1 strict: un record di lettura con formule non va ripassato integralmente a update. Bridge deve definire whitelist/normalizzazione; evitare scarti silenziosi non documentati |
| RETURNING e risultato degli hook | DML adapter base letto (`L/sql/adapters/_gnrbaseadapter.py:797`, `:843`) non emette RETURNING; CRUD update restituisce record | `N/src/asqueel/application_table.py:284`: sovrappone solo campi restituiti con identità di colonna; insert/update restituiscono QueryResult | Non equivalenza di ritorno API. Posthook vede valori DB solo per colonne effettivamente restituite e riconosciute; returning ridotto non è un reload completo |
| Record lazy e invalidazione | `L/sql/gnrsqldata/record.py:313` conserva risultato; `:456` costruisce Bag con resolver | `N/src/asqueel/application_table.py:143`, `:158`: snapshot dict in cache fino a refresh esplicito | V1: nessuna identity map o invalidazione automatica dopo update/rollback/cambio ambiente. Il chiamante deve ricaricare deliberatamente |
| Selection e Bag | `L/sql/gnrsqldata/query.py:446`; `selection.py:256`, `:493`: selection con output, filtri, freeze; `record.py:94`, `:156`: resolver | `N/src/asqueel/application_table.py:127`, `:153`: selection rifiutata, record solo dict | Bridge/futuro separato. Nessun resolver DB viene restituito dal nuovo runtime; non promettere compatibilità Bag |
| aggregateRows | `L/sql/gnrsqldata/record.py:347`, `selection.py:145`: aggregazione delle righe esplose | `N/src/asqueel/compiler.py:443`: rifiuto esplicito | Rimozione deliberata anche dal bridge; non reintrodurre il comportamento dietro selection o record |
| Notifiche e invalidazione applicativa | `L/sql/gnrsql/write.py:50`: totalizzatori, log, `_dbNotify` | `N/src/asqueel/application_table.py:294`: nessuna catena equivalente | Bridge: inventario delle dipendenze. Il notify legacy non dimostra invalidazione universale di ogni record/selection già caricato |
| Import di package e logica | `L/app/gnrapp.py:702` compone mixin; `:713` distingue metodi speciali; `:765` elenca fonti config_db | `N/src/asqueel/application.py:43`: classe esplicita derivata SqlTable; `importers.py:26`: introspezione PostgreSQL | Import schema DB presente, import della logica/package no. Nessuna API `importPackage` trovata nei moduli SQL legacy e sorgenti nuovi ricercati: il requisito va definito, non inferito dal nome |
| Adapter / driver | `L/sql/adapters/_gnrbaseadapter.py:728` contiene anche trasformazioni applicative; execute restituisce cursori | `N/src/asqueel/drivers/psycopg.py:24`, `:62`: binding/driver e risultato materializzato, controllo metadata | Separazione moderna V1, ma estrarre soltanto SQL dall'adapter legacy perderebbe conversioni semantiche |

## Limiti specifici dei nuovi hook

1. **Snapshot corrente, non versione utente.** Il lock protegge il ciclo lettura-modifica del singolo update, ma il metodo non accetta un token di versione né confronta i dati con un vecchio record fornito dal chiamante. Due operazioni serializzate possono entrambe riuscire; non c'è rilevazione implicita di conflitto applicativo.
2. **Old record isolato.** Il prehook può mutare il proprio `old_record` senza cambiare la copia ricevuta dal posthook o il predicato della scrittura. È una differenza concreta dal passaggio del medesimo oggetto nel legacy.
3. **Nuovo record completo ma fisico.** Il merge include tutte le colonne fisiche dichiarate dal modello, non formule SQL, relazioni o campi Python calcolati. Le colonne DB assenti dal modello non entrano automaticamente nello snapshot.
4. **RETURNING parziale.** Un default server o trigger nativo può modificare la riga; il posthook conosce quel nuovo valore solo se ritornato e riconciliabile con una colonna sorgente. Un'espressione con alias non è automaticamente una sostituzione di campo. Questo punto deriva dal sorgente dell'overlay, non da un test di tutti i possibili trigger nativi.
5. **Mutazione del posthook.** I posthook vengono eseguiti dopo il DML: cambiare il dizionario non genera una seconda scrittura e non ricostruisce il QueryResult già restituito dal driver. Una scrittura aggiuntiva deve essere esplicita e partecipa alla sessione comune.
6. **Atomicità limitata al DB.** Gli effetti SQL degli hook nella stessa facciata sono transazionali; file, email o chiamate esterne non vengono annullati dal rollback. Non esiste una coda after-commit applicativa equivalente a quella legacy.
7. **Convenzioni di classi.** Il rilevamento dei nuovi hook confronta i metodi della classe con quelli di SqlTable (`application_table.py:269`); non costituisce il vecchio sistema di mixin da package. Un monkey patch sul solo oggetto non è il contratto supportato.

## Prove disponibili e loro portata

Lettura del legacy e del nuovo repository ai commit dichiarati. Non sono stati eseguiti applicativi legacy completi, né suite differenziali usando le due implementazioni sugli stessi package.

Prove PostgreSQL già eseguite durante l'implementazione, utili come evidenza locale del **nuovo** comportamento:

- `N/tests/application_integration/test_postgres_application.py:62`: visibilità esterna solo al commit; `:81`: rollback/close; `:107` e `:148`: errori hook intercettati restano rollback-only.
- `N/tests/application_integration/test_postgres_application.py:121`: query con ambiente tardivo, compiled stale rifiutata, record cache/refresh e cardinalità.
- `N/tests/application_integration/test_write_hooks.py:97`: snapshot completo, PK composta con zero, old_record separato, pre/post e atomicità cross-table.
- `N/tests/application_integration/test_write_hooks.py:120`: errore posthook update/delete annulla entrambe le tabelle.
- `N/tests/application_integration/test_write_hooks.py:135`: missing, multiple e partizione esterna rifiutati prima degli hook.
- `N/tests/application_integration/test_write_hooks.py:150`: una seconda connessione fallisce con lock_timeout nel prehook, provando che il lock è già acquisito.
- `N/tests/application_integration/test_write_hooks.py:170`: soft delete/restore passa dagli update hook; `:184`: hook cambia PK ma UPDATE individua la vecchia chiave, e tabella senza hook conserva batch.

Ripetizione locale, con PostgreSQL di test attivo:

```sh
GNR_TEST_PG_PORT=55449 /private/tmp/asqueel-v1-venv/bin/python -m pytest tests/application_integration --confcutdir=tests/application_integration --no-cov
```

Non estendere questi risultati a equivalenza di default, Bag, cifratura, counters, trigger di campo/package, transazioni multi-store o compatibilità di un'applicazione importata.

## Decisioni raccomandate per le versioni

**V1 per applicazioni nuove:** mantenere Session condivisa, sync e thread owner; documentare l'alternativa tecnica con autotransazione, hook tabella e cardinalità, snapshot fisico, cache record esplicita, input strict e policy di riga. Servono contratti chiari su RETURNING, valori di default server, errori prima/dopo hook e conflitti concorrenti; non chiamare questa superficie “compatibile legacy” senza qualifiche.

**Bridge successivo:** inventariare le dipendenze di un package campione e classificare separatamente configurazione schema, metodi di dominio, field/package hooks, protezioni, default/counters, conversioni Bag/encrypted/sql_value, cascata, notifiche e callback differite. Un importatore di schema non deve dichiarare importata la logica. Ogni adattamento richiede una prova mirata; aggregateRows resta escluso.

**Futuro:** store/tenant, altri dialetti, oggetti nativi gestiti da migration, eventuale outbox/after-commit, bulk strutturato e streaming. Rivalutare async solo dopo stabilità del nucleo sync. Nessuna di queste capacità deriva automaticamente dall'esistenza di un'interfaccia driver.
