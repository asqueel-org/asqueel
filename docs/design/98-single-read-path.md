# 98 — Percorso unico delle letture

16 ottobre 2026. Worktree `/Users/gporcari/Sviluppo/asqueel/asqueel-read-path`,
branch `codex/core-single-read-path`, base `926000d`.

## Risultato

AsqueelDb, build_database, render operativo, hosting e CLI costruiscono il solo
DbModel gerarchico. La walk generica e finalize restano l'algoritmo di costruzione;
le options precedono le dichiarazioni sulla copia posseduta della source.
Il render `objects_tree` restituisce il modello, il render `objects` lo collega
al database operativo: due prodotti dello stesso renderer, non due costruzioni.
`resolve_model` usa anch'esso questa costruzione. Nessuna conversione a un secondo
ResolvedModel né fallback al compilatore precedente.

Il compilatore gerarchico è ora `asqueel.compiler.QueryCompiler`.
PostgresCompiler sceglie gli adapter per la stessa implementazione.
Eliminati il precedente compilatore/scanner, query_plan.py, _compiler_bindings.py,
object_tree_compiler.py, render(QueryPlan) e prepare(SqlStatement). SQL e kwargs
restano separati; il driver riceve CompiledQuery. Il ramo relations resta
l'autorità per le relazioni e gli handler many restano non implementati.

La tabella operativa rimanda al proprio DbTableObj; SqlColumn e SqlRelation,
che duplicavano i nodi, sono rimossi. x_table_class viene rispettato durante la
costruzione prima dei figli, senza aggiungere composizione di mixin.
Gli identificatori di tabella operativi sono qualificati package.table.
Gli attributi strutturali si leggono sui nodi, senza le precedenti copie .config.

Restano i DTO di catalogo in contracts.py e il loro codec/proiettore: sono
consumati da inspect_postgres, non sono più costruiti dalla source né accettati
come modello del compilatore o database vivo. Non sono una compatibilità
provvisoria per il vecchio percorso di lettura.

## Record e lock

Riferimenti legacy: gnrsqldata/record.py __init__, result, out_dict, out_record,
_loadRecord; gnrsqldata/compiler.py compiledRecordQuery e _recordWhere;
gnrsqldata/query.py:176 per bagFields or for_update.

- Record lazy, snapshot copiato, refresh esplicito. Missing solleva l'errore,
  salvo ignoreMissing=True; più righe restano un errore.
- output dict conserva i valori; output record produce una Bag senza resolver,
  con metadati di colonna e conversione delle X in Bag. Nessuna pyColumn aggiunta.
- Record seleziona i campi fisici, con X incluse per default e senza virtuali
  statiche. Non aggiunge i filtri query draft/deleted/partition per default.
- Una query con lock include le X nell'espansione di *, senza allargare una
  proiezione esplicita. La regola è testata nei due dialetti.
- PostgreSQL conserva FOR UPDATE OF t0. SQLite avvia BEGIN IMMEDIATE a transazione
  chiusa; a transazione aperta esegue UPDATE sulla tabella fisica con assegnazione
  della colonna a sé stessa e WHERE 0. È il raccordo runtime concordato, non un
  algoritmo attribuito all'adapter SQLite legacy (che dichiarava di non gestire
  i lock). Il compilatore trasporta intenzione e identificatori; non apre connessioni.
- Provata la contesa con un secondo writer su entrambi i database; rollback
  rilascia il lock. Nessun cambio di connessione, commit implicito o modifica
  alle righe durante l'acquisizione.

## Scritture

writes.py, triggers.py e runtime.py non sono modificati. Restano i metodi di
scrittura esistenti sulla tabella e il guard gerarchico; non vengono raccordati
in questo lavoro. Il vecchio DML ospitato dal compilatore eliminato non è più
un'API disponibile. La sessione scritture ha confermato che lo sostituisce con
moduli propri, senza QueryPlan/Fragment o vecchi descrittori.

Il confine comune è prepare_sql(sql, kwargs, snapshot) → CompiledQuery →
db.execute(compiled). Gli estremi di relazione e i metadati per il writer sono
nel [contratto 97](97-read-write-contracts.md).

## Test del percorso unico

La selezione riproducibile è `python -m pytest @tests/read_path/pytest.args`.
Raccoglie l'intera suite, escludendo esplicitamente solo i file e le funzioni
che dipendono dal ciclo scritture. Non aggiunge skip, shim o fallback alle API
rimosse. Il dettaglio per il writer è in
[evidence/single-read-path/writer-tests.json](evidence/single-read-path/writer-tests.json).

- Ritirati i contratti di QueryPlan/Fragment/SqlStatement, scanner, vecchio
  modello a descrittori come ingresso del compilatore e vecchi wrapper di colonna.
- I contratti SELECT, binding, relazioni verso uno, formule, macro, count e
  terminali sono quelli già verificati sul nuovo albero. La preparazione degli
  adapter conserva gli oracoli JSON originali, inclusi i fix approvati.
- Portati i test ancora pertinenti di configurazione, composizione, options,
  alias, validazioni, grammatica delle sottoquery, metadati e driver.
  Accessi tramite package.table, columns/virtual_columns, attributes e relations.
- Le quattro raccolte originali formulaColumn sono ora moduli `legacy_*.py`:
  corpi invariati, eseguiti dalle fixture del percorso unico nelle prove di
  compilazione ed esecuzione. Non vengono raccolti anche con la vecchia fixture.
- Ritirate le prove del prodotto cartesiano attraverso relazioni a molti e delle
  vecchie policy allowed/current: restano i contratti concordati many_* senza
  handler e partition con valore corrente scalare.
- SQLite EXISTS: il limite legacy delle doppie parentesi, prima conservato, è
  stato rimosso il 2026-10-16 su decisione dell'utente; le prove eseguono le
  formule `exists=` anche su SQLite.
- Il renderer tollera anche un db senza figli: la configurazione della sola
  connessione è verificata dai test di contesto sui database reali.

Non sono modificati i corpi dei test DML nei file misti. Gli import e i supporti
condivisi seguono l'interfaccia unica; i test scritture restano al writer.
La mappa dei contratti ritirati è in
[read-test-alignment.json](evidence/single-read-path/read-test-alignment.json).

## Verifiche

[Evidenza sintetica](evidence/single-read-path/verification.json), con comando,
conteggi e verifiche statiche. Risultato: **4.253 passed, 12 skipped, 16 deselected**
in 210,70 secondi. I deselected sono i casi scritture nei file misti; altri
27 file dipendenti dal ciclo scritture sono esclusi dalla raccolta. Copertura inclusa:

- entrambi i dialetti, record/lock reali, NamedList, CLI e hosting;
- 74 modelli nativi, attributi/relazioni e JSON migration confrontati con gli
  artefatti indipendenti; applicazione, introspezione e rediff su PostgreSQL;
- Ruff, mypy e Sphinx con warning trattati come errori;
- wheel installata separatamente dal checkout, migration 0.2.2 da PyPI.

La suite generale e la CI integrata non sono dichiarate verdi: i test del ciclo
scritture sono intenzionalmente esclusi dalla selezione letture e richiedono il
lavoro dell'altra sessione. Non è stata eseguita alcuna fusione, pubblicazione o push.
