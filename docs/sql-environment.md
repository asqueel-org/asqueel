# Ambiente SQL per contesto

`SqlEnvironment` raccoglie i valori contestuali di un'operazione applicativa.
Ogni istanza usa un proprio `ContextVar`: scope annidati e task concorrenti
restano separati, senza thread-local globali. L'ambiente non costituisce da solo
un sistema di autorizzazione.

```python
from genro_sql.environment import SqlEnvironment

env = SqlEnvironment({'language': 'it', 'allowed_company_ids': [1, 2]})

with env.temp_env(company_id=1):
    request_values = env.snapshot()
    with env.temp_env(language='en', optional_value=None):
        assert env.current_env['language'] == 'en'
        assert 'optional_value' in env.current_env
    assert env.current_env['language'] == 'it'

assert 'company_id' not in env.current_env
```

## Contratto pubblico

- `SqlEnvironment(defaults=None)`: copia profondamente la mappa iniziale.
- `snapshot()`: restituisce una copia profonda dei valori correnti, racchiusa
  in una mappa esterna di sola lettura.
- `current_env` e `currentEnv`: proprietà equivalenti a una nuova snapshot.
- `temp_env(**values)` e `tempEnv(**values)`: context manager sincroni equivalenti,
  usabili anche all'interno di una funzione async. Sovrappongono i valori allo
  scope corrente e ripristinano lo scope precedente nel `finally`.

`None` è un valore esplicito e non rimuove la chiave. Una chiave assente resta
una condizione distinta da una chiave presente con valore nullo. Un override
sostituisce il valore della chiave: non effettua merge ricorsivi dei dizionari.
Non è prevista la modifica diretta di `current_env`/`currentEnv`.

## Copie, concorrenza e cancellazione

La copia avviene all'inizializzazione, all'ingresso dello scope e a ogni lettura.
Modificare la mappa originale, un suo contenitore annidato o una snapshot già
restituita non modifica l'ambiente attivo. La mappa esterna della snapshot è
immutabile; liste e dizionari annidati sono copie modificabili dal consumer.

I valori devono supportare correttamente `copy.deepcopy`. Un errore di copia
produce `ValueError`, indicando l'operazione e conservando l'eccezione originale
come causa. Un errore all'ingresso non altera lo scope attivo. Un tipo personalizzato
che implementa deepcopy condividendo deliberatamente stato mutabile non offre
le garanzie delle copie dei normali contenitori Python.

Un task figlio eredita il contesto al momento della propria creazione, secondo
la semantica normale di `ContextVar`. Il successivo ripristino del task padre
non modifica il contesto già ereditato dal figlio. Letture e nuovi scope fanno
copie: modifiche ai contenitori di una snapshot e overlay di un task non si
propagano agli altri task. Eccezioni e cancellazione async attraversano il
`finally` dello scope e ripristinano il valore precedente.

## Esecuzione sincrona

Il runtime opera sul thread chiamante. Non copia né propaga il contesto a
worker. ContextVar resta utile per scope annidati e isolamento del contesto,
ma non rende le Bag thread-safe e non introduce operazioni async.

## Integrazione con database e query compilate

`Database(..., environment=env)` e `PostgresDatabase(..., environment=env)`
condividono l'istanza fornita. In assenza di parametro, ogni database crea un
ambiente indipendente. `db.environment` espone l'istanza; `db.current_env`,
`db.currentEnv`, `db.temp_env(...)` e `db.tempEnv(...)` delegano gli stessi contratti.

Il compiler deve ricevere la stessa istanza quando compila usando valori
contestuali. Un `CompiledQuery.environment` presente descrive i valori dai quali
la compilazione dipende: il runtime confronta la snapshot corrente prima di
aprire una connessione o, dentro una transazione, prima di inviare lo statement
al driver. Una discrepanza produce `EnvironmentMismatchError`: ricompilare nel
contesto corretto. Non viene modificato silenziosamente il binding già compilato.
Il vincolo conserva una copia privata: `EnvironmentBinding.values` restituisce
una snapshot scollegata, quindi modificarne contenitori annidati non cambia
i valori usati dalla verifica.

`PsycopgDriver.prepare` conserva il vincolo ambiente dello `SqlStatement` nel
`CompiledQuery`. Le query prive di vincolo ambiente conservano il comportamento
precedente. Il controllo non rende sicuro SQL arbitrario: serve a impedire il
riuso accidentale di una query compilata per un contesto diverso.

## Confini

Il contenitore non seleziona tenant/store. Il compiler risolve `:env_language`
dalla chiave `language` dello snapshot; un parametro esplicito
`params={'env_language': ...}` ha precedenza. Una chiave mancante genera errore,
mentre una chiave presente con None produce un parametro SQL NULL. I parametri
espliciti non introducono dipendenze dall'ambiente. Le
[policy di riga](row-policies.md) consumano lo stesso snapshot e registrano
anche l'assenza delle chiavi che hanno determinato la scelta del filtro.

## Verifiche

`tests/environment/` copre copie e mutazioni, scope annidati, alias, assenza/nullo,
isolamento delle istanze, ereditarietà dei ContextVar e ripristino dopo eccezioni.
I test runtime verificano il vincolo nel driver, il rifiuto delle query fuori
contesto prima dell'I/O e l'immutabilità del vincolo rispetto a mutazioni annidate.
