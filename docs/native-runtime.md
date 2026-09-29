# Runtime SQL sincrono

`Database(driver=...)` gestisce connessioni e transazioni tramite un driver
sincrono iniettato. `PostgresDatabase` seleziona `PsycopgDriver`. Tutte le
operazioni avvengono sul thread chiamante, senza executor, worker o API async.
L'eventuale supporto async verrà valutato dopo il completamento del nucleo.

```python
from genro_sql import PostgresDatabase, CompiledQuery

with PostgresDatabase("dbname=example") as db:
    with db.transaction() as tx:
        result = tx.execute(CompiledQuery(
            'INSERT INTO public.example (name) VALUES (%(name)s) RETURNING id',
            {'name': 'Ada'},
        ))
    result = db.execute(CompiledQuery('SELECT 42 AS answer'))
```

## Transazioni e risorse

Ogni transazione apre una connessione nuova e la chiude all'uscita. Nessun pool
persistente. `db.execute()` apre una transazione per il singolo statement;
per più operazioni atomiche usare `with db.transaction() as tx` e `tx.execute()`.
Transazioni annidate sulla stessa istanza non sono supportate; i contesti sono
monouso. `close()` è idempotente e rifiuta la chiusura durante una transazione
attiva. Un database chiuso non può essere riaperto.

L'uscita senza errori esegue commit; un errore esegue rollback. Un errore del
driver durante execute rende la transazione rollback-only, anche se intercettato
nel corpo del with. In questo caso le altre execute falliscono e l'uscita segnala
`TransactionStateError` dopo il rollback. La validazione offline di profilo e
ambiente precede l'I/O: un rifiuto non rende rollback-only una transazione valida.

`tx.outcome` distingue `not_started`, `active`, `committed`, `rolled_back` e
`unknown`. Un errore durante commit o rollback può rendere incerto l'esito;
non ripetere automaticamente le scritture. La connessione viene comunque chiusa
e lo stato dell'istanza rilasciato, anche se la pulizia solleva un errore.

## Bag e proprietà del thread

Un database appartiene al thread che lo costruisce: accessi da altri thread
sono rifiutati, anche attraverso una transazione. Modello, compiler e Bag
restano nel contesto applicativo. Il runtime non propaga ContextVar verso altri
thread e non invoca resolver Bag in background. Il controllo del thread non
rende thread-safe Bag condivise manualmente dall'applicazione.

`QueryResult.rows` contiene dizionari materializzati. I nomi delle colonne devono
essere univoci e corrispondere ai metadati compilati. Nessun cursore lazy esce
dall'esecuzione. Gli oggetti nei parametri e nei metadati non devono essere
modificati concorrentemente dall'applicazione.

Il runtime è proprietario del controllo transazionale: non inserire comandi
BEGIN/COMMIT/ROLLBACK nelle query applicative. Valori utente in `params`, senza
interpolazione SQL. Le chiamate bloccano fino al completamento; eventuali timeout
si configurano su PostgreSQL. Nessuna cancellazione async o coda di ammissione.

## Ambiente e adapter

Condividere `SqlEnvironment` fra compiler e database per usare `temp_env()` e
le [policy di riga](row-policies.md). Il runtime verifica che le dipendenze
ambientali della query siano ancora valide prima della connessione/esecuzione;
altrimenti solleva `EnvironmentMismatchError`. Gli alias `currentEnv` e `tempEnv`
restano disponibili. Vedi [ambiente SQL](sql-environment.md).

```python
from genro_sql import Database

with Database(driver=my_sync_driver) as db:
    result = db.execute(compiled_query)
```

Il driver implementa `SyncDriver`. La facciata PostgreSQL ammette solo il
profilo `postgresql/psycopg_named`; per altri profili usare `Database`.
`ThreadedDatabase`, `aclose`, `max_workers`, `max_pending` e i protocolli
`async with`/`await execute` sono stati rimossi da questa API alpha.

## Verifiche

Le suite runtime e adapter verificano proprietà del thread, CRUD, metadati,
rollback-only, transazioni monouso, pulizia, chiusura ed errori di commit/rollback.
I test PostgreSQL verificano persistenza e rollback su connessioni reali.
