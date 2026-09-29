# Runtime PostgreSQL nativo V1

`genro_sql.runtime.ThreadedDatabase` espone un'API awaitable su thread dedicati
tramite un driver sincrono iniettato. `PostgresDatabase` conserva l'API PostgreSQL
e seleziona `PsycopgDriver`. Il runtime gestisce risorse e transazioni; il driver
gestisce connessione, esecuzione, risultati e binding. Modello e piano query non
dipendono da psycopg. Vedi [contratto driver](data-driver.md).

```python
from genro_sql.contracts import CompiledQuery
from genro_sql.runtime import PostgresDatabase

async with PostgresDatabase("dbname=example", max_workers=4, max_pending=16) as db:
    async with db.transaction() as tx:
        result = await tx.execute(CompiledQuery(
            'INSERT INTO public.example (name) VALUES (%(name)s) RETURNING id',
            {'name': 'Ada'},
        ))
    # Uscita senza errori: commit terminato; errore: rollback.
    result = await db.execute(CompiledQuery('SELECT 42 AS answer'))
```

## Proprietà e limiti

- Ogni transazione riserva un worker e una connessione nuova; apertura, statement,
  fetch, commit/rollback e chiusura avvengono sullo stesso thread. I thread vengono
  riutilizzati, le connessioni no: nessuno stato di sessione PostgreSQL passa alla
  transazione successiva. Non è ancora un pool di connessioni persistenti.
- `max_workers` limita le connessioni contemporanee. `max_pending` limita le
  richieste in attesa di un worker; oltre il limite viene sollevato
  `DatabaseSaturatedError`. Zero abilita il rifiuto immediato a saturazione.
- `execute()` sul database verifica dialetto e binding prima di acquisire un
  worker o aprire una connessione, poi apre una transazione per la singola operazione.
  Un'operazione composta usa `transaction()`. Le operazioni sulla stessa
  transazione sono serializzate. I contesti transazione sono monouso. Il task
  proprietario non può acquisire una seconda transazione o chiamare db.execute
  dentro quella aperta: usare tx.execute; il tentativo fallisce senza attendere.
- `QueryResult.rows` contiene dizionari materializzati; nessun cursore esce dal
  thread. I nomi dei risultati devono essere univoci. I metadati compilati sono
  preservati; in loro assenza si ricavano i soli nomi dal cursore.
- Una query fallita o cancellata rende la transazione rollback-only, anche se
  l'eccezione viene intercettata dall'applicazione. Ulteriori execute falliscono
  con `TransactionStateError`; l'uscita esegue rollback e, se il chiamante ha
  intercettato l'errore originario, segnala `TransactionStateError` anziché
  presentare una transazione annullata come riuscita.
- La cancellazione dell'await non interrompe la query nel thread: l'await termina
  con cancellazione solo dopo il completamento dell'operazione. Uscendo dal
  contesto si completano rollback/chiusura prima del rilascio del worker.
  Anche cancellazioni ripetute durante l'uscita non abbandonano la pulizia.
- Una cancellazione durante commit **non garantisce rollback**. `tx.outcome`
  distingue `not_started`, `active`, `committed`, `rolled_back`, `unknown`.
  Un errore di comunicazione durante commit produce `unknown`: non riprovare
  automaticamente una scrittura presumendo che non sia avvenuta.
- `aclose()` rifiuta nuove richieste, attende le transazioni attive e termina i
  worker. Chiamarlo dal task che possiede una transazione aperta genera errore
  per evitare deadlock: uscire prima dal contesto. I task applicativi devono
  sempre chiudere i propri contesti. Un'istanza appartiene a un solo event loop.
- Le query compilate rappresentano statement applicativi: il chiamante non deve
  inserirvi comandi di controllo transazionale (`BEGIN`, `COMMIT`, `ROLLBACK`).
  Il runtime è proprietario della transazione. Valori utente esclusivamente in
  `params`; niente interpolazione SQL. La mappa dei parametri è copiata dal
  contratto CompiledQuery, ma i suoi valori restano oggetti applicativi: non
  mutare liste, dizionari, buffer o altri valori fino al completamento dell'await.
  Non viene imposto deepcopy a tipi personalizzati adattabili dal driver.
- Non implementati: streaming, driver async nativo, timeout/cancel server,
  hook di dominio, cluster, retry automatici e pool persistente. Una query che
  non termina trattiene il worker; configurare timeout PostgreSQL appropriati
  con i parametri di connessione o le impostazioni del server.

## Verifiche

Test deterministici in `tests/native_runtime/test_runtime.py`: affinità del thread,
rollback-only, saturazione, cancellazione ripetuta durante query/commit, chiusura,
esito incerto del commit. `test_postgres.py` usa `GENRO_SQL_TEST_DSN` per CRUD,
RETURNING, rollback e responsività dell'event loop su un database di prova reale.

## Iniezione del driver

```python
from genro_sql.runtime import ThreadedDatabase

async with ThreadedDatabase(driver=my_sync_driver, max_workers=4) as db:
    result = await db.execute(compiled_query)
```

Il driver implementa `SyncDriver`, incluse validazione del profilo e operazioni
I/O. `PostgresDatabase(driver=...)` ammette driver alternativi soltanto con
profilo `postgresql/psycopg_named`; per altri profili usare `ThreadedDatabase`.
Ogni operazione I/O resta sul worker della transazione; la validazione offline
del profilo avviene prima della chiamata al worker. Errori originali del driver
sono propagati senza wrapping; fallimenti I/O mantengono la semantica rollback-only.
Un errore di validazione prima dell'I/O non modifica lo stato della transazione.
