# Casi d'uso — database creati da ricette Builder

Gli esempi mostrano l'API obiettivo. Il vocabolario esiste già, mentre firme
complete, validator e `SqlMigrationRenderer` devono ancora essere implementati.

## 1. Database minimale

```python
from asqueel import SqlBuilder


class RecipeDatabase(SqlBuilder):
    def main(self, root):
        db = root.db(name="recipes")
        public = db.schema(name="public")

        author = public.table(
            name="author",
            pkey="id",
            comment="Authors of recipes",
        )
        author.column(name="id", dtype="serial")
        author.column(
            name="name",
            dtype="A",
            size="0:120",
            notnull=True,
            comment="Public author name",
        )
```

Il risultato non è ancora SQL: è un albero interrogabile che può essere
validato, documentato, mostrato in una GUI o inviato a consumer differenti.

## 2. Relazione, constraint e index

```python
class RecipeDatabase(SqlBuilder):
    def main(self, root):
        db = root.db(name="recipes")
        public = db.schema(name="public")

        author = public.table(name="author", pkey="id")
        author.column(name="id", dtype="serial")
        author.column(name="name", dtype="A", size="0:120", notnull=True)

        recipe = public.table(name="recipe", pkey="id")
        recipe.column(name="id", dtype="serial")
        recipe.column(name="title", dtype="A", size="0:160", notnull=True)

        author_id = recipe.column(name="author_id", dtype="L", notnull=True)
        author_id.relation(
            to="public.author.id",
            foreign_key=True,
            on_delete="CASCADE",
            back_reference="recipes",
            one_name="Author",
            many_name="Recipes",
        )

        recipe.constraint(
            name="uq_recipe_author_title",
            constraint_type="UNIQUE",
            columns="author_id,title",
        )
        recipe.constraint(
            name="ck_recipe_title",
            constraint_type="CHECK",
            check_clause="char_length(title) > 0",
        )
        recipe.index(
            name="ix_recipe_title",
            columns={"title": None, "id": "DESC"},
        )
```

La relation contiene due informazioni distinte:

- navigazione applicativa e nomi semantici;
- vincolo fisico, abilitato da `foreign_key=True`.

Il renderer delle migrazioni esporta soltanto la seconda parte.

## 3. Creazione o allineamento del database

API indicativa:

```python
from genro_builders.builder import BuilderHandler
from asqueel.renderers import SqlMigrationRenderer
from asqueel_migration import PgDatabase, SqlMigrator, StructureValidator


model = RecipeDatabase()
BuilderHandler().add_builder(model)

desired = SqlMigrationRenderer(builder=model).render()
desired = StructureValidator().validate(desired)

database = PgDatabase(
    {"dbname": "recipes", "host": "localhost"},
    application_schemas=["public"],
)
migrator = SqlMigrator(database)
migrator.ormStructure = desired
migrator.prepareMigrationCommands()

print(migrator.getChanges())   # sempre revisionare prima
# migrator.applyChanges()      # azione esplicita
```

Il nome definitivo dell'API dovrà seguire le convenzioni reali dei renderer di
`genro-builders`. L'esempio definisce il flusso, non congela ancora la firma.

## 4. Generazione algoritmica da dati esterni

Una ricetta Python può costruire tabelle o indici da metadati senza introdurre
un linguaggio di macro:

```python
TABLES = {
    "country": [("id", "serial"), ("name", "A")],
    "city": [("id", "serial"), ("name", "A"), ("country_id", "L")],
}


class GeoDatabase(SqlBuilder):
    def main(self, root):
        schema = root.db(name="geo").schema(name="public")

        for table_name, fields in TABLES.items():
            table = schema.table(name=table_name, pkey="id")
            for field_name, dtype in fields:
                table.column(name=field_name, dtype=dtype)
```

Il vantaggio non è poter scrivere qualsiasi codice, ma mantenere leggibile una
regola realmente algoritmica usando il linguaggio già noto.

## 5. Blocchi riusabili

Pattern applicativi come audit fields o indirizzi non devono diventare nuovi
elementi del core. Possono essere funzioni o struct method che materializzano
colonne reali:

```python
def audit_fields(table):
    table.column(name="created_at", dtype="DHZ", notnull=True)
    table.column(name="updated_at", dtype="DHZ", notnull=True)


def address_fields(table, prefix):
    table.column(name=f"{prefix}_street", dtype="A", size="0:160")
    table.column(name=f"{prefix}_city", dtype="A", size="0:80")
    table.column(name=f"{prefix}_postal_code", dtype="A", size="0:16")
```

La recipe resta esplicita e l'albero risultante contiene normali column,
visibili a validator e renderer.

## 6. Metadati semantici che non migrano

```python
recipe.column(
    name="title",
    dtype="A",
    size="0:160",
    notnull=True,
    name_long="Recipe title",
    group="content",
    widget="TextBox",
)
```

`dtype`, `size` e `notnull` appartengono al piano fisico. `name_long`, `group`
e `widget` restano nel modello semantico e possono guidare runtime o GUI. Un
golden test deve dimostrare che non entrano nel normalized JSON.

## 7. Evoluzione della recipe

Versione 1:

```python
recipe.column(name="title", dtype="A", size="0:160")
```

Versione 2:

```python
recipe.column(name="title", dtype="A", size="0:240", notnull=True)
recipe.index(name="ix_recipe_title", columns={"title": None})
```

La recipe descrive lo stato desiderato. `asqueel-migration` confronta tale
stato con il database e produce le sole operazioni necessarie. Il builder non
deve contenere una sequenza manuale di migration imperative.

## 8. PostgreSQL specializzato

Una futura composizione può rendere esplicito il backend:

```python
class PostgresRecipeDatabase(SqlBuilder, PostgresElements):
    def main(self, root):
        db = root.db(name="recipes")
        db.extension(name="pg_trgm")
        public = db.schema(name="public")
        public.dbtype(name="recipe_status", type_kind="ENUM",
                      enum_values=["draft", "published", "archived"])
```

Il core deve poter rappresentare un tipo nativo attraverso `sql_type`, ma la
grammar PostgreSQL può documentare e validare enum, domain, range e composite
type con precisione maggiore.

## 9. Criteri per gli esempi ufficiali

Ogni esempio dovrebbe mostrare tre viste sincronizzate:

1. recipe Python;
2. albero o normalized JSON;
3. DDL/diff prodotto.

Ogni esempio che applica modifiche deve usare un database temporaneo e
verificare che il secondo diff sia vuoto.
