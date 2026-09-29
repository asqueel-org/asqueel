# Consegna: nucleo sincrono e policy di riga

29 settembre 2026. La decisione aggiornata è completare il nucleo sincrono
prima di valutare async. Sostituisce il runtime awaitable della prima V1.

## API e confini

- `Database` con driver iniettato e `PostgresDatabase`: `with`, `transaction()`,
  `execute()`, `close()` sincroni. Connessione e chiamate sul thread costruttore;
  accessi da altri thread rifiutati. Nessun executor o passaggio delle Bag ai worker.
- Rimossi `ThreadedDatabase`, `DatabaseSaturatedError`, `aclose`, `max_workers`,
  `max_pending` e protocolli async. È una modifica incompatibile dell'API alpha;
  esempi e test applicativi sono aggiornati. Nessun alias async fittizio.
- Transazioni monouso, connessione nuova per transazione, commit/rollback,
  rollback-only dopo errore I/O, esito incerto esplicito, chiusura garantita anche
  in caso di errore commit/rollback. Rifiutati nesting e rientro durante execute.
- `SqlEnvironment`, `current_env/currentEnv`, `temp_env/tempEnv`: scope annidati,
  snapshot distaccati e ripristino. Query compilate vincolate alle dipendenze
  ambientali, inclusa l'assenza delle chiavi; cambiamento rilevato prima dell'I/O.
- Modello: `RowPolicies` e `PartitionScope`; dichiarazioni builder `x_partition`,
  `x_partitions`, `x_draft_field`, `x_logical_deletion_field` validate.
- Compiler: partition multiple AND, falsy validi, NULL esplicito, allowed vuoto
  senza righe, contesto mancante in errore, intersezione current/allowed.
  Protezione delle scritture su partition locali e completamento INSERT.
- Draft esclusi con `IS NOT TRUE`; tombstone esclusi con `IS NULL`. Inclusione
  esplicita e mark con valore originale su proiezioni fisiche scalari.
  `soft_delete()` e `restore()` dedicati; `delete()` rimane fisico.

## Verifiche effettuate

| Verifica | Risultato |
|---|---|
| Suite completa Python 3.12, PostgreSQL 17 locale dedicato | 337 test superati, inclusi 24 PostgreSQL |
| Copertura complessiva | 95%; runtime 100% delle istruzioni |
| Wheel installata Python 3.13, fuori dal checkout | 313 test superati, 24 PostgreSQL esclusi in questo gate |
| Wheel core-only Python 3.11, senza migration/driver client | Modello, emissione, compiler e adapter offline riusciti |
| Ruff, mypy, controllo whitespace | Riusciti |
| Build wheel | Riuscita |
| Demo sincrona con adapter espliciti su PostgreSQL | CRUD, metadati e rollback riusciti; schema temporaneo rimosso |

I test PostgreSQL verificano anche scope relazionali, combinazione con OR
applicativi, policy soltanto sulla tabella radice, 0/False/NULL, allowed vuoto,
soft delete, restore e rifiuto del riuso fuori contesto. I test runtime verificano
anche errori di commit/rollback/close e nessuna chiamata driver da altri thread.
I test storici del workflow restano invariati; le verifiche di worker/cancellazione
del precedente runtime sono sostituite dai contratti sincroni pertinenti.

## Limiti espliciti

Partition relazionali supportate in lettura; scritture rifiutate salvo bypass
esplicito. Store, tenant, subtable, partizioni fisiche PostgreSQL e hook di dominio
restano successivi. Nessuna reintroduzione di aggregateRows. Le policy del
compiler non sostituiscono autorizzazioni o RLS del database. Le chiamate SQL
sono bloccanti; async è rinviato, non simulato.

Contratti dettagliati: [runtime](native-runtime.md), [ambiente](sql-environment.md),
[policy](row-policies.md). I rapporti V1 precedenti conservano la storia delle
relative consegne e non definiscono il runtime corrente.
