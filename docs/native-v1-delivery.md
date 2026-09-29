# V1 nativa PostgreSQL — implementazione e verifiche

29 settembre 2026. Profilo alpha per **applicazioni nuove**, sviluppato da tre
agenti con integrazione e revisione incrociata. Non è un rilascio pubblicato
né una promessa di sostituzione del runtime legacy. V1 è il nome del traguardo;
la versione del package non è stata promossa a 1.0.

Aggiornamento successivo: [compiler, adapter dati e driver](data-adapters-delivery.md)
sono stati separati preservando le facciate V1. I conteggi sotto descrivono
il collaudo iniziale; il rapporto adapter contiene le verifiche successive.

## Funzionalità implementate

| Area | API e risultato |
|---|---|
| Contratti | `ResolvedModel`, `Table`, `Column`, `Relation`, `CompiledQuery`, `QueryResult`; separazione fra identità logica, nome fisico e metadati. |
| Risoluzione | `resolve_model(builder, ui=...)`: naming schema/prefisso/override, provenienza, metadati UI inline/paralleli e formule semplici. |
| Import | `inspect_postgres(connection, schemas, ui=...)`: cataloghi PostgreSQL espliciti, PK/FK composite, tipi normalizzati, default, indici e report dei limiti. |
| Compiler | `PostgresCompiler`: SELECT, parametri nominati, alias, filtri, ordine, limit/offset, relazioni to-one, formule, CRUD e RETURNING. |
| Runtime | `PostgresDatabase`: API awaitable, connessione e thread riservati alla transazione, ammissione limitata, rollback e cancellazione drenata. |
| Migrazioni | `to_physical_builder(model)`: mapping fisico comune al compiler, ponte al migratore esistente con rifiuto delle proiezioni non fedeli. |
| Composizione | Ricette modulari della grammatica comune collaudate su validator, catalogo, emitter, resolver e proiezione. |

L'import non inventa identità persistenti dal catalogo: inizialmente coincidono
con i nomi. Per preservare l'identità di una colonna dichiarata attraverso un
rename si usa `x_identity`. Gli overlay UI rimangono esterni e si riapplicano
al reimport; non viene introdotto un archivio persistente nascosto.

## Contratti operativi

- Ogni transazione ha una connessione nuova e un thread dedicato; il thread
  viene riutilizzato, la connessione no. Commit, rollback e fetch restano fuori
  dall'event loop. I risultati sono materializzati.
- Il numero di worker e la coda d'ammissione sono limitati. Operazioni annidate
  che richiederebbero una seconda transazione nello stesso task sono rifiutate.
- Un errore rende la transazione rollback-only; se intercettato dall'applicazione,
  l'uscita segnala comunque l'annullamento. Nessun commit apparente.
- Cancellare l'await non interrompe la query PostgreSQL: si attende la conclusione
  e la pulizia prima del rilascio. Il chiamante può configurare timeout server.
  Una cancellazione/errore durante commit non giustifica un retry automatico.
- I valori usano binding. Espressioni, formule e SQL raw restano codice
  applicativo fidato, non input SQL libero da utenti finali.
- `aggregateRows` è rifiutato; nessun regrouping o deduplica implicita delle righe.

## Risultati della revisione

La revisione ha corretto wildcard su nomi quotati, identità dei risultati,
validazione dell'unicità nelle relazioni, rollback-only, ammissione durante la
chiusura e perdite nel ponte verso il migratore.

L'import conserva le informazioni anche quando non può proiettarle in DDL.
I warning accompagnano sia `ImportResult` sia `ResolvedModel`: un modello
importato incompleto non diventa una specifica distruttiva di migrazione.
La proiezione rifiuta i warning e le semantiche non rappresentabili, comprese
collation particolari, dipendenze da sequenze, determinate opzioni degli indici
e azioni FK non supportate. Vedere il [contratto del modello](native-model.md).

I test storici delle issue #8/#9 passano con il migratore PyPI 0.1.0 e sono
tornati asserzioni ordinarie. Il confronto esteso ha inoltre individuato nella
nuova proiezione un diff spurio: il metodo predefinito btree era dichiarato
esplicitamente mentre il reader lo normalizza come assente. La proiezione usa
ora la stessa normalizzazione; il caso DESC parziale resta nella verifica di
idempotenza. Questo risultato non certifica ogni variante delle issue, né ne
cambia lo stato su GitHub.

I montaggi annidati Builders conservano gli indirizzi per nome. Non vengono
adottati come nuova struttura del package: la prova evidenzia limiti delle
firme consultate dal validator e della serializzazione di configurazioni
contenenti classi. La [nota di composizione](native-composition.md) distingue
i percorsi verificati dalle limitazioni sperimentali.

## Verifica riproducibile

Ambiente isolato Python 3.12, PostgreSQL 17 UTF-8 temporaneo sulla porta 55449;
nessun database applicativo esistente modificato. Ogni test nativo usa oggetti
univoci e cleanup/rollback. Le dipendenze Genro sono le ultime stabili verificate
su PyPI: Builders/Bag 0.27.0, TYTX 0.16.0, Toolbox 0.14.0, migratore 0.1.0,
Routes 0.30.1, ASGI 0.46.3. Driver psycopg 3.3.6.

| Verifica finale | Esito |
|---|---|
| Suite completa Python 3.12 + PostgreSQL 17, profilo ASGI/Routes | **202 passati**, nessuno skipped o xfail; 18 test PostgreSQL. |
| Copertura della suite completa | **94%** complessiva. |
| Wheel Python 3.13 fuori dal checkout | **184 passati**, 18 test PostgreSQL esclusi intenzionalmente dal profilo unitario. |
| Wheel Python 3.11 senza driver/migratore | Costruzione modello, validazione, emitter, resolver e compiler riusciti. |
| Demo nativa PostgreSQL | Naming, UI, CRUD async e rollback riusciti; schema temporaneo rimosso. |
| Ruff e mypy | Superati. |
| Distribuzione | sdist e wheel costruiti; risorse e import verificati fuori dal checkout. |

La baseline precedente conteneva 124 test: i nuovi contratti aggiungono 78 casi.
Le verifiche locali non sono una nuova esecuzione della CI remota.

```bash
python -m pip install -r requirements/asgi.txt
python -m pip install --no-deps -e .
GNR_TEST_PG_PORT=55449 python -m pytest
ruff check src tests scripts
mypy src/genro_sql
python -m build --no-isolation
GENRO_SQL_DEMO_DSN='host=127.0.0.1 port=55449 user=postgres dbname=postgres' \
  python scripts/demo_native.py
```

I test PostgreSQL richiedono un servizio di prova: non si dichiarano riusciti
saltandoli quando il servizio manca. `pytest -m 'not postgresql'` è il profilo
unitario, distinto dal collaudo completo. È disponibile anche l'override
`GENRO_SQL_TEST_DSN` per i test dei singoli componenti.

## Limiti e versioni successive

Restano fuori dalla V1: import e bridge legacy, virtualRelation GEP operative,
scope/subtable applicativi, query Bag e consumer legacy, hook/cluster, driver
async nativo, streaming, pool persistente, altri dialetti runtime e gestione
di view/funzioni/trigger/partizioni fisiche. Le sintassi avanzate non supportate
falliscono esplicitamente; non vengono emulate.

Il percorso proposto resta [V2-A semantica, V2-B adozione legacy, V3 prestazioni
e portabilità, V4 oggetti nativi](design/07-release-proposal.md). Il piano
generale P0–P8 mantiene il suo valore di indirizzo e non viene marcato concluso
solo perché il sottoinsieme V1 è implementato.
