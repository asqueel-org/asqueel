# Runtime SQL sincrono

`Database(driver=...)` possiede il lifecycle delle connessioni.
`PostgresDatabase` seleziona `PsycopgDriver`; `AsqueelDb` usa la configurazione
applicativa. Le operazioni eseguono su una `SessionDb`, una per chiamata.

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
    db.closeConnection()
```

## Transazioni e risorse

La connessione selezionata si apre al primo execute. Le operazioni successive
condividono la transazione pendente fino a `commit()` o `rollback()` espliciti.
Non esiste un metodo `transaction()`. `tempEnv` modifica
il contesto e può selezionare una connessione nominata; non conclude transazioni.

Un errore SQL provoca rollback automatico, compreso il lavoro precedente non
committato, e pulisce le callback della connessione. L'errore originale viene
rilanciato. Un errore Python dentro una scrittura o callback precommit impone
rollback prima del riuso. Un errore postcommit non annulla i dati già salvati;
le callback non raggiunte restano fino al recupero applicativo. Se la callback
fallita ha aperto nuovo lavoro SQL, quel lavoro richiede rollback.

Un errore del driver durante commit/rollback può lasciare un esito incerto:
non ripetere automaticamente le scritture. La connessione viene scartata.
`closeConnection()` fa rollback e chiude la connessione della sessione; la
sessione resta utilizzabile e l'istruzione successiva apre una nuova
connessione. `with db.session() as s:` apre la sessione principale della
chiamata con un `currentEnv` nuovo e la chiude all'uscita. La conclusione durante hook o callback
è protetta dai controlli di rientranza.

## Thread, ambiente e driver

Modello e configurazione stanno nell'`AsqueelDb` condiviso da tutte le
chiamate. Connessioni, callback, ambiente e trigger stack stanno nella
`SessionDb` della chiamata; la sessione corrente sta in un `ContextVar`
dell'`AsqueelDb`, quindi ogni contesto `contextvars` è una chiamata separata.
Una sessione può passare tra thread della sua chiamata; l'uso concorrente
solleva `TransactionStateError`. Ogni chiamata deve chiudere le proprie sessioni. Non condividere i record interni delle connessioni.
Le classi applicative condivise non devono conservare stato di richiesta negli
attributi. Questo contratto non rende thread-safe oggetti Bag condivisi e mutati
manualmente, né rende il runtime async-safe.

Il compiler standalone può condividere un `SqlEnvironment` con il runtime.
Il DB applicativo usa `ApplicationEnvironment` per `currentEnv`, workdate e
locale. I parametri `:env_*` di una query compilata sono riletti dall'ambiente
corrente a ogni esecuzione.

Il driver implementa `SyncDriver`. La facciata PostgreSQL ammette il profilo
`postgresql/psycopg_named`; per altri profili usare `Database` con il driver
appropriato o la configurazione applicativa. `execute` restituisce il cursore
aperto, come il legacy; le righe si leggono per nome.

Il runtime possiede il controllo transazionale: non inserire BEGIN/COMMIT/ROLLBACK
nelle query applicative. I valori utente vanno nei parametri; le espressioni SQL
sono codice applicativo fidato. Le chiamate sono bloccanti. La futura migrazione
async è analizzata nel [documento 26](design/26-async-portability.md).

## Verifiche

Le suite runtime verificano isolamento per chiamata, sessioni nominate,
CRUD, callback, rollback, cleanup ed errori di completamento. PostgreSQL e SQLite
sono esercitati su connessioni reali. `scripts/demo_native.py` verifica il
percorso PostgreSQL con commit/rollback espliciti e uno schema temporaneo.
