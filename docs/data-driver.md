# Data driver: binding ed esecuzione

Il confine tra dialetto SQL e driver è `SqlStatement`: una sequenza di testo e
nodi `Parameter`, con valori e metadati risultato separati. Gli identificatori
sono già quotati dal dialetto; il driver non analizza nuovamente l'SQL.

`BindingFormatter.prepare(statement)` restituisce un `CompiledQuery` con
`dialect` e `binding` espliciti. `SyncDriver` estende il contratto con `validate`,
`connect`, `execute`, `commit`, `rollback` e `close`. Il runtime `ThreadedDatabase`
invoca il driver su thread dedicati e non interpreta l'SQL.

## PsycopgDriver

Il profilo implementato è `postgresql/psycopg_named`. L'import del modulo e la
preparazione del binding funzionano senza installare/importare psycopg; il
pacchetto esterno viene caricato soltanto in `connect` ed `execute`.

```python
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.query_plan import Parameter, SqlStatement

statement = SqlStatement(
    ('SELECT 12 % 5 AS remainder WHERE ', Parameter('enabled')),
    {'enabled': True},
)
compiled = PsycopgDriver().prepare(statement)
assert compiled.sql == 'SELECT 12 %% 5 AS remainder WHERE %(enabled)s'
```

Il formatter:

- raddoppia `%` soltanto nelle parti testuali per il protocollo psycopg;
- traduce ogni `Parameter(name)` in `%(name)s`, senza interpolare il valore;
- accetta nomi ASCII corrispondenti a `[A-Za-z_][A-Za-z0-9_]*`;
- rifiuta parametri mancanti, parti sconosciute e dialetti incompatibili;
- conserva soltanto i valori effettivamente referenziati e conserva i metadati;
- non modifica `SqlStatement`: ripetere prepare sullo stesso statement produce
  lo stesso risultato, senza accumulare escaping.

Non passare a prepare SQL già preparato: l'ingresso richiede `SqlStatement` e
rifiuta `CompiledQuery`. Literal, commenti e identificatori contenenti `%`
seguono lo stesso escaping testuale, senza essere scambiati per parametri.

## Query costruite direttamente e compatibilità

`CompiledQuery(sql, params, columns)` conserva i default PostgreSQL/psycopg.
La costruzione diretta è un percorso di basso livello: l'SQL deve già usare il
binding del driver, compreso il raddoppio dei percentuali letterali quando si
passa la mappa parametri a psycopg. `validate` verifica tipo e profilo, **non**
riscrive né riparsa l'SQL diretto. Il percorso compiler → statement → formatter
fornisce invece il trattamento strutturale dei parametri.

La mappa viene copiata dal contratto; oggetti mutabili contenuti nei valori
restano dell'applicazione e non vanno modificati prima del completamento dell'await.

## Esecuzione e risultati

`execute` verifica nuovamente il profilo prima di accedere alla connessione,
crea un cursore con row factory a tuple, esegue con SQL e parametri separati,
materializza le righe e chiude il cursore. I nomi restituiti devono essere univoci;
quando mancano metadati compilati vengono ricavati i soli nomi del risultato.
Se presenti, i metadati compilati devono corrispondere a numero, nomi e ordine
delle colonne del cursore: la verifica precede il fetch. Una discrepanza o
metadati su uno statement senza result set produce errore e rollback nel runtime.
Tipo, UI e provenienza dei metadati coerenti restano invariati.
Nessun cursore lazy esce dal worker.

Il driver non decide quando aprire o chiudere una transazione: runtime e contesto
sono proprietari di quel ciclo di vita. `commit`, `rollback` e `close` delegano
alla connessione; gli errori originali restano riconoscibili dall'applicazione.
Non vengono introdotti retry automatici né classificazioni che mascherano gli
errori del driver. `autocommit=True` è rifiutato dal percorso transazionale.

## Verifiche

`tests/adapter_driver/` copre percentuali e placeholder, parametri ripetuti/mancanti,
profili incompatibili, esecuzione con driver fittizio senza psycopg, affinità del
thread e propagazione degli errori. Un processo separato blocca ogni import di
psycopg e verifica formatter offline e runtime con driver iniettato.
I test lifecycle di `tests/native_runtime/` restano invariati: cancellazioni,
chiusura, saturazione e rollback continuano a essere responsabilità del runtime.
