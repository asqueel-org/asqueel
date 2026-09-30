# Compiler PostgreSQL nativo — profilo iniziale

`asqueel.compiler.PostgresCompiler` compila il modello risolto condiviso in
`CompiledQuery(sql, params, columns)`. Non apre connessioni e non esegue query.
È un primo profilo nativo, non il compiler compatibile con tutto il legacy.

## Confini fra compiler, dialetto e driver

`QueryCompiler(model, dialect, formatter)` risolve il linguaggio Genro in un
`QueryPlan`: tabella fisica, proiezioni, join, predicato, assegnamenti e metadati.
I frammenti distinguono testo SQL fidato, `Identifier` e `Parameter`; non
contengono quoting di identificatori né placeholder del driver.

I metodi `plan_select`, `plan_insert`, `plan_update` e `plan_delete` hanno gli
stessi argomenti delle operazioni corrispondenti e restituiscono il piano senza
renderizzarlo. `compile_plan(plan)` delega `dialect.render(plan)` e poi
`formatter.prepare(statement)`. I metodi `select`/`insert`/`update`/`delete`
eseguono entrambe le fasi e restituiscono il `CompiledQuery` pronto per il runtime.

Il dialetto possiede il lexer SQL e la generazione delle istruzioni. Per esempio,
dollar quote, stringhe E e cast `::` appartengono al lexer PostgreSQL; lo scanner
comune vede token protetti e risolve soltanto i riferimenti Genro. Il formatter
possiede placeholder e escaping richiesti dal driver. Un dialetto e un formatter
con identità incompatibili vengono rifiutati.

`PostgresCompiler(model)` rimane la facciata che sceglie `PostgresDialect` e
`PsycopgDriver`, preservando le firme e i risultati del profilo iniziale. La
compilazione non apre connessioni. I protocolli non implicano supporto ad altri
database: serve un adapter realmente implementato e verificato.

La funzione storica `compiler.quote_identifier` conserva per compatibilità
quoting PostgreSQL **e** escaping psycopg, delegando i due passaggi agli adapter.
Nuovo codice che manipola piani deve usare `Identifier`; codice del dialetto può
usare `dialect.quote_identifier`, che non applica escaping del driver.

## API

```python
compiler = PostgresCompiler(model)
query = compiler.select(
    'sales.invoice',
    columns='$id, @customer.name AS customer_name, $total',
    where='$total >= :minimum',
    params={'minimum': 100},
    order_by='$id',
    limit=20,
)
```

Sono disponibili:

- `select(table, columns='*', where=None, params=None, order_by=None, limit=None, offset=None)`;
- `insert(table, values, returning='*')`;
- `update(table, values, where, params=None, returning='*')`;
- `delete(table, where, params=None, returning='*')`.

I nomi in `values` sono logici; i valori vengono sempre associati a parametri.
`returning=None` disabilita RETURNING; insert con `{}` produce DEFAULT VALUES. Se `*` include una formula
che richiede un join, il RETURNING DML viene rifiutato: selezionare esplicitamente
le colonne supportate oppure leggere la formula con una query successiva.
Update richiede almeno un valore. Update e delete richiedono un predicato non
vuoto; `where='TRUE'` rende esplicita una modifica di tutte le righe. Non si tratta
comunque di una verifica delle autorizzazioni applicative.

## Espressioni e confini

`$column` risolve nome e formula nel modello. La forma `$"display name"`
consente nomi logici con spazi, trattini, Unicode e altri caratteri; una doppia
virgoletta interna si scrive raddoppiata, come in `$"a""b"`. Wildcard e RETURNING
usano questa risoluzione anche per le colonne importate con nomi arbitrari. `@relation.column` percorre relazioni
dichiarate to-one con LEFT JOIN, riutilizzando il join per il medesimo percorso.
Sono possibili più segmenti; chiavi composte producono condizioni con AND.
Il target deve avere nel modello una chiave primaria o un vincolo di unicità
riconosciuto per le colonne del join; questo controllo vale anche per modelli
creati direttamente tramite dataclass. Il compiler non interroga il database
per verificare che la dichiarazione corrisponda ai vincoli realmente installati.

Le formule SQL elementari possono riferire altre colonne e formule. I cicli
vengono rifiutati. Le chiavi di join devono essere colonne fisiche. I percorsi
di relazione non sono ammessi nelle primitive DML di questo profilo.

`columns` accetta una stringa separata da virgole oppure una sequenza di
espressioni; lo scanner riconosce parentesi, stringhe e commenti. `*` espande
le colonne dichiarate, incluse le formule. Una colonna diretta mantiene nome,
dtype e UI; `ResultColumn.source` conserva `Column.identity` quando dichiarata,
altrimenti il percorso logico completo. Alias di proiezione e override dei nomi
fisici non modificano questa identità. Un percorso riceve un nome con underscore o un alias `AS` esplicito.
Le espressioni SQL calcolate richiedono un alias; non ricevono dtype/UI inventati.
Alias duplicati vengono rifiutati.

Le espressioni SQL sono **codice applicativo fidato**. Lo scanner protegge
stringhe SQL, stringhe E, identificatori quotati, dollar quote e commenti anche
annidati, ma non è un parser completo PostgreSQL o una barriera per SQL fornito
dagli utenti. I dati esterni vanno sempre in `params`. `:name` diventa binding
nominato psycopg; `::type` resta un cast PostgreSQL. Un parametro richiesto ma
assente genera errore. Parametri forniti e non utilizzati non vengono inoltrati.

Semicolon di separazione istruzioni e macro Genro non supportate vengono
rifiutati. Non sono implementati l'espansione delle macro legacy, gli ingressi
Bag, le virtualRelation GEP, la semantica delle policy legacy, il planner di
aggregazioni, GROUP BY/HAVING come opzioni API o il bridge record/selection.
SQL aggregato esplicitamente scritto può essere passato come espressione,
per esempio `COUNT(*) AS count`; ciò non implica copertura della semantica
aggregata legacy. `aggregateRows` è rifiutato esplicitamente e non viene emulato.

## Esecuzione e percentuali

Il runtime deve eseguire **sempre con il mapping dei parametri, anche vuoto**:

```python
cursor.execute(query.sql, dict(query.params))
```

L'SQL prodotto usa `%(name)s` per i binding e `%%` per percentuali letterali,
anche dentro stringhe e identificatori, come richiesto dal percorso parametrico
psycopg. Non eseguire `query.sql` omettendo il secondo argomento e non interpolare
il mapping con Python. Le proprietà del modello governano schema e nome fisico;
il compiler quota separatamente i componenti.

## Verifiche

La suite `tests/native_compiler/` controlla scanner, cast, commenti, parametri,
quote, alias, formule/cicli, riuso dei join, metadata, valori DML, collisioni dei
binding, predicati obbligatori e rifiuto delle funzionalità escluse. Queste sono
prove di compilazione; la verifica PostgreSQL end-to-end è distinta e appartiene
alla suite di integrazione del runtime.
