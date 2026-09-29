# Adapter dati — estrazione dalla V1

29 settembre 2026. Implementazione del [piano 08](design/08-data-adapters-plan.md).
PostgreSQL rimane l'unico dialetto dati concreto; psycopg rimane l'unico driver
DB concreto. I fake dei test verificano le interfacce, non certificano supporto
di ulteriori backend.

## Componenti consegnati

| Componente | Responsabilità effettiva |
|---|---|
| `QueryCompiler` | Riferimenti Genro, formule, relazioni, unicità del target, alias, metadati e costruzione del piano risolto. |
| `QueryPlan` e frammenti | Tabelle fisiche, join, proiezioni, assegnazioni, clausole, parametri e descrizione dei risultati; identificatori e binding restano nodi distinti dal testo SQL. |
| `PostgresDialect` | Scanner PostgreSQL, quoting SQL, resa SELECT/CRUD/RETURNING, LEFT JOIN, paginazione, capacità del profilo e validazione dei piani. |
| `PsycopgDriver` | Preparazione offline dei parametri, escaping del protocollo, client psycopg, cursori, fetch e primitive transazionali. |
| `ThreadedDatabase` | Proprietà della sessione, worker, ammissione, serializzazione, cancellazione e pulizia, tramite driver iniettato. |
| `PostgresCatalogProvider` | Introspezione strutturale read-only, conservando le verifiche di fedeltà dell'importatore V1. |

I protocolli `DataDialect`, `BindingFormatter`, `SyncDriver` e `CatalogProvider`
definiscono i confini; non importano il client DB o il migratore per definire
i rispettivi contratti.

```text
modello + richiesta Genro
    → QueryCompiler.plan_* → QueryPlan
    → PostgresDialect.render → SqlStatement
    → PsycopgDriver.prepare → CompiledQuery
    → ThreadedDatabase → PsycopgDriver.execute → QueryResult
```

Il piano risolto non contiene placeholder psycopg e non applica l'escaping
del driver. Lo statement del dialetto contiene identificatori già quotati e
nodi `Parameter`. Soltanto `prepare` produce `%(name)s` e raddoppia i `%`
letterali, compresi quelli dentro stringhe, commenti e nomi. Non viene cercato
o sostituito testo simile a un placeholder nell'SQL finale.

## Uso e compatibilità

```python
from genro_sql import QueryCompiler, PostgresDialect, PsycopgDriver, ThreadedDatabase

driver = PsycopgDriver()
compiler = QueryCompiler(model, PostgresDialect(), driver)
query = compiler.select('sales.invoice', columns='$id, $total',
                        where='$total >= :minimum', params={'minimum': 100})

async def read(conninfo):
    async with ThreadedDatabase(conninfo, driver=driver) as database:
        return (await database.execute(query)).rows
```

Per ispezionare i passaggi si usano `plan_select`, `plan_insert`, `plan_update`,
`plan_delete` e `compile_plan`. La normale API SELECT/CRUD continua a restituire
direttamente `CompiledQuery`.

`PostgresCompiler(model)` e `PostgresDatabase(...)` restano facciate compatibili
che selezionano le implementazioni PostgreSQL. I tre argomenti posizionali
esistenti di `CompiledQuery(sql, params, columns)` restano validi; i nuovi
campi `dialect` e `binding` hanno default PostgreSQL/psycopg. Uno statement
preparato con un altro profilo viene rifiutato prima dell'apertura di una
connessione. I costruttori raw mantengono la responsabilità applicativa sulla
correttezza del testo SQL dichiarato per quel profilo.

L'SQL di `CompiledQuery` conserva il contratto V1: è già preparato per psycopg
e deve essere eseguito con la mappa dei parametri, anche vuota. Non va passato
nuovamente a `prepare`. La funzione storica `compiler.quote_identifier`
mantiene il precedente escaping del driver; il nuovo
`PostgresDialect.quote_identifier` produce invece solo quoting SQL.

Gli identificatori oltre 63 byte UTF-8 vengono ora rifiutati dal dialetto
anziché affidarsi al troncamento del server. È un controllo esplicito aggiunto
per evitare collisioni; il limite si applica anche agli alias generati.

## Capacità e confine strutturale

Le capability descrivono il sottoinsieme implementato e possono essere
ristrette per un profilo: SELECT, singole operazioni DML, RETURNING distinto
per operazione, LEFT JOIN, limit/offset e DEFAULT VALUES. Non dichiarano
supporto per upsert, COPY, streaming, locking avanzato o tutte le versioni
e le estensioni PostgreSQL. Le funzioni SQL raw conservano il dialetto di
provenienza; non sono tradotte automaticamente in un altro linguaggio SQL.

sqlmigration rimane proprietario degli adapter DDL e del diff strutturale.
Il provider di catalogo resta separato dal dialetto dati: la facciata
`inspect_postgres` delega al provider PostgreSQL senza perdere i warning su
RLS, oggetti non gestiti, sequenze, collation e constraint. Non sono state
introdotte dipendenze inverse o modifiche al repository del migratore.

Quoting dati/DDL è confrontato con casi comuni; i nomi fisici arrivano dallo
stesso modello. Il reader normalizzato del migratore non sostituisce ancora
il catalogo più ricco: l'[inventario delle differenze](data-dialects.md)
documenta ciò che deve essere preservato prima di una futura convergenza.

## Verifiche

La suite preserva i 202 test V1 e aggiunge verifiche di piano neutrale,
parametri strutturati, capacità mancanti, profili incompatibili prima della
connessione, quoting dati/struttura e compilazione senza dipendenze opzionali.
Il percorso esplicito degli adapter viene inoltre eseguito su PostgreSQL.

| Verifica finale | Esito |
|---|---|
| Suite completa, Python 3.12 e PostgreSQL 17 UTF-8 | **265 passati**, nessuno skipped o xfail; 21 test PostgreSQL. |
| Copertura completa | **94%**. |
| Wheel Python 3.13 fuori dal checkout | **244 passati**, 21 test PostgreSQL intenzionalmente esclusi dal profilo unitario. |
| Wheel Python 3.11 senza driver/migratore installati | Modello, emitter, compiler e pipeline degli adapter riusciti. |
| Demo facciate V1 e demo adapter espliciti | Entrambe riuscite su PostgreSQL, con CRUD e rollback. |
| Ruff, mypy, sdist e wheel | Superati. |

Sono stati aggiunti 63 casi rispetto alla baseline V1. La revisione incrociata
ha inoltre corretto i commenti SQL finali nei frammenti dei piani manuali,
che potevano inglobare clausole successive, e il controllo di corrispondenza
fra metadati dichiarati e colonne effettive del cursore. In caso di mismatch
la transazione fallisce e viene annullata; il caso è verificato sul DB reale.

Questi sono risultati locali con le dipendenze stabili già verificate nella
V1; non costituiscono una nuova esecuzione della CI remota. L'istanza PostgreSQL
temporanea usa la porta 55449 e non coinvolge database applicativi esistenti.

La demo mantiene il percorso con le facciate e offre quello con adapter iniettati:

```bash
GENRO_SQL_DEMO_DSN='host=127.0.0.1 port=55449 user=postgres dbname=postgres' \
  python scripts/demo_native.py --explicit-adapters
```

Entrambi usano uno schema temporaneo univoco e lo eliminano dopo CRUD e rollback.

I gate A0–A4 del piano sono completati per l'estrazione PostgreSQL: contratti,
componenti separati, integrazione, confine strutturale e consegna verificata.
La convergenza futura dei reader tra repository rimane un lavoro separato.

## Cosa resta successivo

Driver async nativo, secondo dialetto e ampliamenti della semantica Genro sono
interventi distinti. Questa separazione consente di aggiungerli senza replicare
resolver o lifecycle. Non cambia i limiti funzionali V1 e non reintroduce
aggregateRows, hook legacy o migrazioni non rappresentabili.
