# Piano per completare la grammar e la pipeline SQL

## 1. Obiettivo della prima release utile

Permettere di descrivere un database con una ricetta `SqlBuilder`, ottenere un
normalized JSON valido e usare `asqueel-migration` per creare o allineare un
database reale.

Non è necessario completare contemporaneamente runtime model, query compiler,
DDL totale e round-trip idiomatico.

## 2. Architettura delle dipendenze

```text
genro-builders
      ↑
  asqueel ─────────────→ asqueel-migration
 grammar + renderer          contratto + diff + writer
```

- `asqueel` dipende da `genro-builders`.
- L'integrazione migration di `asqueel` può dipendere da
  `asqueel-migration`, preferibilmente tramite extra opzionale.
- `asqueel-migration` non deve dipendere da `asqueel`.

## 3. Slice A — contratto fisico minimo

Limitare il primo verticale a:

- db;
- schema;
- table;
- column;
- primary key singola e composta;
- UNIQUE singola e composta;
- CHECK;
- foreign key singola e composta;
- index;
- commenti di tabella e colonna;
- extension già supportate dal contratto.

### Attività

1. Rendere esplicite e tipizzate le firme in `modern/elements.py`.
2. Documentare ogni parametro, il mapping JSON e la portabilità.
3. Aggiungere tipi/enum per dtype, azioni FK, constraint type e index order.
4. Aggiungere validator di dominio eseguiti quando l'albero è completo.
5. Congelare fixture di esempio prima di scrivere il renderer.

### Criteri di accettazione

- una recipe valida costruisce l'albero atteso;
- ogni parametro noto compare nell'export della grammar;
- collocazioni e cardinalità errate falliscono con path leggibile;
- riferimenti inesistenti falliscono prima della migrazione;
- i metadati aperti restano nell'albero ma sono distinguibili dal piano fisico.

## 4. Slice B — `SqlMigrationRenderer`

Il renderer vive in `asqueel`, perché conosce la semantica degli elementi.
Deve produrre un dizionario normalizzato, non necessariamente una stringa JSON.

### Regole

- Creare una struttura nuova a ogni render: il migratore può annotare
  transitoriamente l'input.
- Usare le factory pubbliche di `asqueel-migration`.
- Non duplicare `clean_attributes`, `hashed_name` o le regole pkey.
- Esportare soltanto elementi fisici.
- Ignorare correttamente aliasColumn, formulaColumn, subQueryColumn e pyColumn.
- Esportare relation soltanto quando `foreign_key=True`.
- Conservare ordine e sort direction degli index.
- Applicare `StructureValidator` al confine pubblico.
- Segnalare feature non supportate; mai eliminarle silenziosamente.

### Mapping minimo

| SqlBuilder | normalized JSON |
|---|---|
| `db(name)` | `new_structure_root(name)` |
| `schema(name)` | `new_schema_item(name)` |
| `table(name, pkey, comment)` | `new_table_item`; `attributes.pkeys/comment` |
| `column(...)` | `new_column_item` filtrato da `COL_JSON_KEYS` |
| `relation(foreign_key=True)` | `new_relation_item` |
| `constraint(UNIQUE/CHECK)` | `new_constraint_item` |
| `index(...)` | `new_index_item` |
| `extension(name)` | `new_extension_item` |
| `eventTrigger` | solo se il contratto/capability corrente lo supporta |

### Golden oracle

La stessa struttura descritta come recipe e come human JSON deve convergere:

```python
assert SqlMigrationRenderer(model).render() == (
    JsonStructureProducer(human_json).get_json_struct()
)
```

Confrontare semanticamente, senza dipendere da formattazione JSON.

## 5. Slice C — uso reale con il migratore

Integrare l'output validato:

```text
recipe → normalized JSON desiderato
DB reader → normalized JSON reale
diff → report SQL → apply esplicito
```

Testare inizialmente con SQLite in processo e poi con PostgreSQL effimero.

### Sicurezza

- preview del diff prima dell'applicazione;
- DROP disabilitati per default;
- distinzione fra errore di connessione e database inesistente;
- nuova struttura a ogni preparazione;
- test di idempotenza: dopo apply, il secondo diff è vuoto;
- nessuna applicazione automatica in esempi o test senza flag esplicito.

## 6. Slice D — separazione backend

Creare un core portabile e mixin specifici, senza anticipare astrazioni non
necessarie.

### Core indicativo

- schema, table, column;
- pkey, unique, check, FK;
- index nelle capacità condivise;
- tipi normalizzati;
- commenti.

### PostgreSQL indicativo

- database options, schema owner/authorization;
- extension ed event trigger;
- enum, domain, composite e range type;
- generated/identity columns specifiche per versione;
- index method, expression, opclass, INCLUDE, NULLS order, partial index,
  storage parameters e concurrently;
- partitioning, inheritance, tablespace, row security;
- view/materialized view;
- function/procedure;
- sequence;
- table trigger.

Una feature PostgreSQL entra nella grammar soltanto quando esistono almeno
renderer o migration capability, reader e test di idempotenza.

## 7. Slice E — DDL renderer diretto

Il renderer diretto è utile per:

- preview di una singola entità;
- bootstrap senza confronto;
- documentazione ed esempi;
- dialect test puntuali.

Iniziare da PostgreSQL `CREATE TABLE`, ma non usarlo come sostituto del
migratore incrementale. Riutilizzare quoting, type mapping e writer esistenti
quando possibile; evitare una seconda implementazione divergente del DDL.

## 8. Slice F — entità avanzate

Ordine consigliato, coerente con le dipendenze:

1. CHECK e commenti;
2. view e materialized view;
3. function/procedure e table trigger;
4. enum/domain/composite/range type;
5. sequence;
6. extension/event trigger;
7. partitioning e policy, se richiesti da casi reali.

Per view e CHECK, PostgreSQL riscrive le espressioni durante l'introspezione:
non confrontare ingenuamente il testo originale con quello restituito dal
catalogo. Seguire la strategia di canonicalizzazione definita nella roadmap di
`asqueel-migration`.

## 9. Matrice di test

Per ogni feature fisica:

| Livello | Verifica |
|---|---|
| Grammar | firma, parent/child, cardinalità, tipo parametro |
| Validator | riferimenti e invarianti cross-node |
| Projection | normalized JSON atteso |
| Writer | SQL esatto per il dialetto |
| Integration | apply su DB effimero |
| Round-trip | introspection semanticamente equivalente |
| Idempotence | secondo diff vuoto |
| Negative | errore esplicito e non distruttivo |

## 10. Definition of done

Una slice è completa quando:

- codice, test e documentazione concordano;
- grammar export descrive tutti i parametri noti;
- normalized JSON passa `StructureValidator`;
- l'integrazione non inverte le dipendenze;
- il caso positivo e quello negativo sono testati;
- l'esempio è eseguibile;
- le feature non supportate generano errore o warning strutturato;
- il comportamento è idempotente sul database target.
