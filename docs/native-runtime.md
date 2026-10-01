# Runtime SQL sincrono

`Database(driver=...)` possiede il lifecycle delle connessioni.
`PostgresDatabase` seleziona `PsycopgDriver`; `AsqueelDb` usa la configurazione
applicativa. Tutte le operazioni eseguono sul thread chiamante.

```python
from asqueel import PostgresDatabase, CompiledQuery

db = PostgresDatabase("dbname=example")
try:
    result = db.execute(CompiledQuery(
        'INSERT INTO public.example (name) VALUES (%(name)s) RETURNING id',
        {'name': 'Ada'},
    ))
    db.commit()
except Exception:
    db.rollback()
    raise
finally:
    db.close()
```

## Transazioni e risorse

La connessione selezionata si apre al primo execute. Le operazioni successive
condividono la transazione pendente fino a `commit()` o `rollback()` espliciti.
Non esistono oggetti Session né un metodo `transaction()`. `tempEnv` modifica
il contesto e può selezionare una connessione nominata; non conclude transazioni.

Un errore SQL provoca rollback automatico, compreso il lavoro precedente non
committato, e pulisce le callback della connessione. L'errore originale viene
rilanciato. Un errore Python dentro una scrittura o callback precommit impone
rollback prima del riuso. Un errore postcommit non annulla i dati già salvati;
le callback non raggiunte restano fino al recupero applicativo. Se la callback
fallita ha aperto nuovo lavoro SQL, quel lavoro richiede rollback.

Un errore del driver durante commit/rollback può lasciare un esito incerto:
non ripetere automaticamente le scritture. La connessione viene scartata.
`closeConnection()` ripulisce tutte le connessioni del thread corrente e permette
il riuso del DB nella richiesta successiva. `close()` chiude lo stato DB di quel
thread; è idempotente e non committa. La conclusione durante hook o callback
è protetta dai controlli di rientranza.

## Thread, ambiente e driver

Modello e handle del DB possono essere condivisi tra thread. Connessioni,
callback e `ApplicationEnvironment` sono isolati per thread; ogni worker deve
ripulire le proprie risorse. Non condividere i record interni delle connessioni.
Le classi applicative condivise non devono conservare stato di richiesta negli
attributi. Questo contratto non rende thread-safe oggetti Bag condivisi e mutati
manualmente, né rende il runtime async-safe.

Il compiler standalone può condividere un `SqlEnvironment` con il runtime.
Il DB applicativo usa `ApplicationEnvironment` per `currentEnv`, workdate e
locale. Le dipendenze ambientali di una query compilata vengono verificate
prima dell'esecuzione; una query non più valida solleva `EnvironmentMismatchError`.

Il driver implementa `SyncDriver`. La facciata PostgreSQL ammette il profilo
`postgresql/psycopg_named`; per altri profili usare `Database` con il driver
appropriato o la configurazione applicativa. `QueryResult.rows` contiene
risultati materializzati; nessun cursore lazy esce dall'esecuzione.

Il runtime possiede il controllo transazionale: non inserire BEGIN/COMMIT/ROLLBACK
nelle query applicative. I valori utente vanno nei parametri; le espressioni SQL
sono codice applicativo fidato. Le chiamate sono bloccanti. La futura migrazione
async è analizzata nel [documento 26](design/26-async-portability.md).

## Verifiche

Le suite runtime verificano isolamento per thread, connessioni nominate,
CRUD, callback, rollback, cleanup ed errori di completamento. PostgreSQL e SQLite
sono esercitati su connessioni reali. `scripts/demo_native.py` verifica il
percorso PostgreSQL con commit/rollback espliciti e uno schema temporaneo.
