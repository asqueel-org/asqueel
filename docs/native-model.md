# Modello nativo e importazione PostgreSQL V1

`resolve_model(builder, *, ui=None)` in `asqueel.model` risolve una ricetta
`SqlBuilder` già costruita e validata nei contratti `ResolvedModel`, `Table`,
`Column`, `Relation`. Non modifica la ricetta e non richiede il migratore.

## Nomi e metadati

Lo schema logico resta la chiave del modello (`sales.invoice`). Gli attributi
`x_sql_schema` e `x_sql_prefix` si ereditano dallo schema alla tabella;
`x_sql_prefix=True` significa schema logico seguito da underscore, una stringa
è un prefisso esatto, `False` lo disabilita. `x_sql_name` sulla tabella prevale
sul prefisso; sulla colonna indica il nome fisico esatto. Non si deducono nomi
logici dagli underscore. Collisioni fisiche sono errori.

Ogni colonna ha identità predefinita `schema.tabella.colonna`, sostituibile con
`x_identity` persistente deciso dall'applicazione. Per conservare l'identità dopo
un rename occorre quindi dichiararla esplicitamente: non esiste inferenza automatica.
`attributes` conserva gli attributi dichiarati e la provenienza; il contenitore
esterno è immutabile, i valori annidati sono metadati applicativi.

I metadati `x_ui` sono arricchiti dall'overlay `ui` per percorso logico e infine
per identità esplicita. Non è consentito ridefinire tipo, formula, nome SQL,
chiave, unicità o obbligatorietà nell'overlay UI. Non sono richiesti widget.

```python
model = resolve_model(builder, ui={
    'sales.invoice.total': {'label': 'Totale', 'format': '#,##0.00'},
})
column = model.table('sales.invoice').columns['total']
```

Le formule V1 usano `formulaColumn(sql_formula=...)`; la stringa è codice SQL
applicativo affidabile, la sua compilazione appartiene al compiler. Alias virtuali,
provider Python e colonne subquery sono respinti dal resolver. Le relazioni
forward devono puntare a una chiave primaria o univoca dichiarata: `one_one`
non sostituisce questa garanzia. Il nome navigabile è la colonna/composito
proprietario, oppure `x_name` sulla relazione. Non vengono generate inverse.
Le [policy di riga](row-policies.md) dichiarano partition logiche, draft e
cancellazione logica. Subtable, tenant, store e altre estensioni partition
non riconosciute sono respinti: non vengono silenziosamente ignorati.

## Importazione read-only

`inspect_postgres(connection, schemas, *, ui=None)` in `asqueel.importers`
restituisce `ImportResult(model, warnings)`. La connessione è psycopg sincrona;
il chiamante possiede transazione, snapshot e chiusura. Per una fotografia
coerente con DDL concorrente usare una transazione con isolamento appropriato.
L'importatore non esegue DDL, commit, rollback né cancellazioni.

```python
result = inspect_postgres(connection, ['sales'], ui=overlay)
model = result.model
for warning in result.warnings:
    print(warning)
```

Gli schemi vanno indicati esplicitamente. Sono importate tabelle ordinarie,
colonne con tipo PostgreSQL completo, default, nullability, identity/generated,
commenti, PK anche composite e FK navigabili verso tabelle importate. I nomi
fisici sono anche i nomi logici iniziali. Le FK importate si navigano usando il
nome del constraint, così più FK fra le stesse tabelle rimangono distinguibili.

`Table.attributes['constraints']` conserva definizioni e dettagli del catalogo;
`['indexes']` conserva `pg_get_indexdef`, predicate, validità e unicità, compresi
DESC, indici espressivi e parziali. Sono metadati fedeli del catalogo, non un
piano di migrazione né una promessa di round-trip DDL tramite il migratore.
I tipi comuni importati sono normalizzati nei codici Genro (`integer` → `I`,
`character varying` → `A`); il tipo PostgreSQL completo resta in `raw_type`.
Tipi senza codice rimangono verbatim e producono warning, senza conversioni
arbitrarie. La proiezione fisica rifiuta le conversioni note come lossy.

Viste, materialized view, foreign table, partizioni e tabelle partizionate non
entrano nel runtime V1 e producono warning; così trigger applicativi, routine,
RLS e FK verso tabelle non importate. L'importatore non rivendica un inventario
universale di tutti gli oggetti PostgreSQL. Le sequence sono segnalate come non gestite; ruoli, permessi,
policy e dipendenze estese non sono modellati. Colonne generated/identity sono
preservate: i vincoli di scrittura restano applicati dal database.

Per conservare l'interfaccia al reimport mantenere l'overlay separato e passarlo
nuovamente; l'importazione non dispone di un archivio UI persistente. Nessuna
importazione legacy è inclusa in questa V1 per nuove applicazioni.

## Verifiche

I test in `tests/native_model` controllano naming, overlay e provenienza,
rifiuto di semantiche non supportate e cardinalità non garantite. Il test
PostgreSQL, attivabile con `ASQUEEL_TEST_DSN`, crea uno schema univoco dentro
una transazione e annulla tutto alla fine: verifica PK/FK composite, default,
indice DESC/parziale, warning per viste e reimport stabile con overlay.

## Bridge verso il migratore

`asqueel.projection.to_physical_builder(model)` crea una nuova ricetta con
nomi fisici risolti, da passare a `SqlMigrationRenderer`. Proietta colonne,
PK/FK, UNIQUE, default e indici semplici anche DESC/parziali. Formule e UI non
sono DDL. Gli indici del catalogo con espressioni, INCLUDE, collazioni/opclass
personalizzate, ordine NULL non standard, opzioni avanzate o stato invalido
sono respinti; così colonne identity/generated, constraint non supportati e
FK verso tabelle esterne al modello. Il fallimento è esplicito, senza omissione.

I nomi arbitrari dei constraint importati non sono rappresentabili nella
pipeline attuale. Il comportamento predefinito è quindi rifiutare la
proiezione dei constraint; `allow_constraint_rename=True` abilita l'equivalenza strutturale
solo quando il successivo confronto del migratore usa
`ignore_constraint_name=True`. Non autorizza una rinomina in produzione.
I nomi originali rimangono nei metadati importati. La gestione e creazione
indipendente delle sequence resta fuori perimetro: i default dipendenti da
sequence e le colonne serial con ownership rilevata sono respinti dalla
proiezione, pur rimanendo leggibili nel modello importato.

Ogni warning di importazione è presente sia in `ImportResult.warnings` sia in
`ResolvedModel.warnings`. La proiezione rifiuta un modello con warning, senza
opzione per ignorarli: include schemi richiesti inesistenti, RLS, viste, trigger,
routine e sequence non gestiti. Questa barriera impedisce di presentare al
migratore un catalogo parziale come se fosse completo; il runtime può comunque
usare le tabelle importate per leggere.

Sono rilevati e respinti anche collazioni di colonna personalizzate, FK con
`ON DELETE SET NULL/DEFAULT` limitato a un sottoinsieme delle colonne e opzioni
non rappresentabili degli indici posseduti da constraint (incluso fillfactor).
Le FK importate usano `indexed=False`: gli indici già presenti sono proiettati
dal catalogo, senza aggiungerne uno automaticamente.

La regressione PostgreSQL verifica ora un vero confronto attraverso
`SqlMigrator(ignore_constraint_name=True, removeDisabled=False)` sulla stessa
transazione: nessun comando per il modello importato con PK/FK composite,
default e indice DESC parziale. Il metodo predefinito `btree` viene normalizzato
ad assente come nel reader del migratore; conservarlo esplicitamente causava
un DROP/CREATE spurio, ora corretto nella proiezione. Non è una correzione del
migratore né evidenza di risoluzione generale delle sue issue storiche.
