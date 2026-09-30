# Progetto del transpiler — normalized JSON verso recipe Python

## 1. Obiettivo

Partire dal JSON normalizzato prodotto dai reader di `asqueel-migration` e
generare una recipe Python `SqlBuilder` semanticamente equivalente alla
struttura fisica del database.

Pipeline:

```text
database reale
    ↓ reader asqueel-migration
normalized JSON
    ↓ SqlModelReader
source tree SqlBuilder
    ↓ SqlPythonEmitter
recipe Python
```

Separare reader ed emitter è preferibile a un'unica conversione diretta:

- il reader risolve il mapping semantico;
- il source tree può essere validato e renderizzato di nuovo;
- l'emitter si occupa soltanto di produrre Python deterministico;
- GUI e altri importer possono riusare il reader;
- il test può confrontare gli alberi prima della qualità stilistica del codice.

## 2. Garanzia realistica

Il JSON letto dal database contiene il **piano fisico**. Non può ricostruire:

- metadati UI o nomi localizzati;
- formule e colonne Python non materializzate;
- relazioni puramente logiche senza foreign key;
- componenti e funzioni usati dalla recipe originale;
- cicli, condizioni e astrazioni originarie;
- comportamento applicativo delle classi di tabella.

La promessa corretta è:

> database → recipe fisicamente equivalente

Non è:

> database → recupero della recipe e dell'intenzione originali

Il codice generato è una baseline fedele che una persona o un LLM può
rifattorizzare mantenendo golden test di equivalenza.

## 3. Input

Accettare inizialmente soltanto il contratto normalizzato validato:

```python
normalized = StructureValidator().validate(reader.get_json_struct(...))
```

Non legare il transpiler alle righe grezze dei cataloghi PostgreSQL. I reader di
`asqueel-migration` sono già il livello responsabile delle differenze fra
dialetti.

## 4. Mapping verso il source tree

| normalized JSON | source tree moderno |
|---|---|
| root | `db(name=entity_name)` |
| schemas[name] | `schema(name=name)` |
| tables[name] | `table(name=name, pkey=..., comment=...)` |
| columns[name] | `column(name=name, **physical_attributes)` |
| single-column FK | `column(...).relation(...)` |
| multi-column FK | decisione su compositeColumn, vedi §5 |
| UNIQUE singola | `column(unique=True)` |
| UNIQUE composta | `constraint(constraint_type="UNIQUE", ...)` |
| CHECK | `constraint(constraint_type="CHECK", ...)` |
| indexes | `index(...)` preservando ordine e sort |
| extensions | `extension(name=...)` nel mixin backend |
| event_triggers | elemento backend se supportato |

Gli hash strutturali sono identità interne del contratto. L'emitter dovrebbe
preferire il nome leggibile esplicito quando presente e non usare l'hash come
nome di dominio, salvo assenza di alternative.

## 5. Problema principale: foreign key composte

Il normalized JSON esprime direttamente:

```json
{
  "columns": ["country_code", "city_code"],
  "related_schema": "geo",
  "related_table": "city",
  "related_columns": ["country_code", "code"]
}
```

La grammar moderna corrente pone ogni relation sotto una colonna e usa
`compositeColumn` per chiavi multiple. Un reader fedele deve sapere come
nominare sia il composite locale sia quello target.

Alternative da prototipare con fixture:

1. **Composite sintetici deterministici**: il reader crea compositeColumn con
   nomi derivati dalle colonne. Mantiene la grammar attuale, ma aggiunge nodi
   non presenti fisicamente nel catalogo.
2. **Elemento physicalForeignKey di tabella**: rappresenta esattamente il
   contratto e può essere sugarizzato in relation per authoring. Introduce una
   seconda forma concettuale.
3. **Relation con liste esplicite**: estendere relation affinché un importer
   possa indicare `columns` e `related_columns`, lasciando la forma annidata
   come API ergonomica.

Criteri di scelta:

- round-trip senza perdita;
- leggibilità della recipe generata;
- unicità e stabilità dei path;
- una sola semantica per validator e migration renderer;
- compatibilità con navigazione runtime;
- assenza di collisioni con compositeColumn dichiarate dall'utente.

Non implementare il multi-column round-trip prima di registrare questa
decisione.

## 6. `SqlModelReader`

Responsabilità:

- validare la versione del contratto;
- creare il builder/source tree senza passare da testo Python;
- preservare ordine significativo di schema, table, column e index;
- convertire soltanto attributi conosciuti;
- conservare eventuali estensioni sconosciute in un namespace esplicito o
  fallire secondo modalità strict;
- risolvere la rappresentazione delle FK dopo aver letto tutte le tabelle;
- produrre diagnostiche con path JSON e path del source tree.

Due passaggi consigliati:

1. creare database, schemi, tabelle e colonne;
2. aggiungere constraint, relation e index quando tutti i target esistono.

## 7. `SqlPythonEmitter`

Output minimo:

```python
from asqueel import SqlBuilder


class ImportedDatabase(SqlBuilder):
    def main(self, root):
        db = root.db(name="recipes")
        public = db.schema(name="public")
        author = public.table(name="author", pkey="id")
        author.column(name="id", dtype="serial")
        author.column(name="name", dtype="A", size="0:120", notnull=True)
```

Regole di emissione:

- output deterministico;
- identificatori Python locali sanificati e separati dai nomi SQL;
- stringhe emesse con quoting sicuro;
- keyword in ordine canonico;
- omettere default impliciti soltanto se il round-trip resta identico;
- usare variabili per db/schema/table, chaining soltanto quando migliora la
  leggibilità;
- non emettere hash interni se esiste un nome esplicito;
- aggiungere commento `TODO` per feature conservate ma non rappresentabili;
- modalità `literal` fedele prima di una futura modalità `idiomatic`.

Usare un generatore AST o una piccola IR di statement, non concatenazioni
fragili sparse nel traversal.

## 8. Test fondamentale di round-trip

```text
normalized JSON A
    ↓ reader
source tree
    ↓ emitter
Python
    ↓ esecuzione controllata
source tree ricostruito
    ↓ SqlMigrationRenderer
normalized JSON B

assert semantic_equal(A, B)
```

Il confronto deve usare le stesse regole di normalizzazione del migratore.

Fixture minime:

- schema vuoto e tabella minimale;
- tutti i dtype normalizzati;
- tipo SQL nativo sconosciuto;
- pkey singola e composta;
- unique singola e composta;
- CHECK;
- FK singola e composta;
- azioni FK e deferred;
- index multicolonna con DESC, where, method, tablespace e with_options;
- commenti con quoting e Unicode;
- extension ed event trigger;
- nomi SQL non validi come identificatori Python;
- due schema con tabelle omonime.

## 9. Integrazione con il database reale

Test PostgreSQL completo:

1. creare un database/schema fixture con DDL noto;
2. leggerlo con `PgReader`;
3. generare la recipe;
4. eseguire la recipe in ambiente controllato;
5. proiettarla con `SqlMigrationRenderer`;
6. confrontarla con il JSON iniziale;
7. verificare diff vuoto.

Ripetere il sottoinsieme portabile con SQLite, MySQL e MSSQL secondo le
capability dichiarate.

## 10. Rifinitura assistita da LLM

Dopo aver ottenuto codice literal verificato, un LLM può:

- estrarre blocchi riusabili;
- riconoscere convenzioni ripetute;
- rinominare variabili locali;
- separare tabelle in componenti o sub-builder;
- aggiungere documentazione.

Ogni trasformazione deve rieseguire il golden round-trip. Il modello non deve
giudicare equivalenza soltanto leggendo il codice.
