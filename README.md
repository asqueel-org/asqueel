# Genro SQL

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/asqueel/svg/asqueel-wordmark-inverse.svg">
  <img src="assets/asqueel/svg/asqueel-wordmark-primary.svg" alt="Asqueel — Genro SQL" width="360">
</picture>

Define SQL models in Python, compile parameterized queries, and work with
PostgreSQL through a synchronous API. Genro SQL keeps logical names, physical
database names, relationships, and column UI metadata in a shared model.

The developer manual describes the intended delivery contract, including designed
features. See [Current status](docs/guide/limitations.md) for implementation
availability and open decisions.

## Install

```sh
python -m pip install "genro-sql[postgresql]"
```

Use `genro-sql` for model building and offline compilation only. Add the
`migration` extra to use the separate schema migration integration. From a
checkout, run `python -m pip install -e ".[postgresql]"` in the repository root.

## Build an application database

Declare the model and connection configuration in one recipe:

```python
from genro_sql import SqlDatabaseConfig, build_database


class Shop(SqlDatabaseConfig):
    def main(self, root):
        db = root.db("shop", conninfo="dbname=shop")
        customer = db.schemas().schema("sales").tables().table("customer", pkey="id")
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", x_ui={"label": "Customer name"})


with build_database(Shop) as db:
    customer = db.table("sales.customer")
    query = customer.query(
        columns="$id, $name", where="$id >= :minimum_id",
        params={"minimum_id": 1}, order_by="$id",
    )
    print(query.sqltext)  # Compiles without opening a connection.
```

Against an existing `sales.customer` table, call `query.fetch()` to get a list
of dictionaries. Table writes and reads share a lazy session. Use `db.commit()`
and `db.rollback()`, or group operations with `with db.transaction():`.
Closing the database rolls back pending work; `with db:` does not commit it.

Construction does not connect or create tables. The
[runnable quickstart](docs/guide/quickstart.md) includes explicit disposable
schema setup and cleanup. [Configuration](docs/guide/configuration.md) explains
layered recipes and live table objects. The separate compiler and low-level
runtime remain available for advanced integrations.

Query expressions are application code; pass external values through parameters
rather than SQL interpolation.

## Learn and use Genro SQL

Start with [What is Genro SQL?](docs/guide/overview.md) and
[the object model](docs/guide/concepts.md), run the
[quickstart](docs/guide/quickstart.md), then follow the
[customers and invoices tutorial](docs/guide/tutorial.md). The tutorial includes a
[complete runnable script](docs/guide/_examples/shop_tutorial.py) with assertions,
transaction examples and disposable-schema cleanup.

| You want to… | Read |
|---|---|
| Configure an application and render live objects | [Configuration](docs/guide/configuration.md) |
| Declare names, relations, aliases and UI metadata | [Models](docs/guide/models.md) |
| Read data or load exactly one record | [Queries](docs/guide/queries.md) |
| Insert, update or delete | [Writes](docs/guide/writes.md) and [transactions](docs/guide/transactions.md) |
| Add business behavior | [Table hooks](docs/guide/hooks.md) |
| Define computed values and correlated subqueries | [Formulas](docs/guide/formulas.md) |
| Scope data by organization, draft or deletion state | [Environment](docs/guide/environment.md) and [row policies](docs/guide/row-policies.md) |
| Start from an existing database or manage its schema | [Importing](docs/guide/importing.md) and [migrations](docs/guide/migrations.md) |
| Come from Genropy | [For Genropy users](docs/guide/legacy.md), including agreed differences |
| Come from SQLAlchemy | [For SQLAlchemy users](docs/guide/for-sqlalchemy.md) |
| Come from Django | [For Django users](docs/guide/for-django.md) |
| Come from Peewee | [For Peewee users](docs/guide/for-peewee.md) |
| Look up a call or diagnose a problem | [API cheat sheet](docs/guide/cheatsheet.md) and [troubleshooting](docs/guide/troubleshooting.md) |

For advanced integration, see [cascading grammars](docs/guide/configuration-grammars.md),
[the compiler](docs/guide/compiler.md), [low-level execution](docs/guide/low-level-runtime.md)
and [adapters](docs/guide/adapters.md).

The public Sphinx site contains these English guides and the API reference.
To build it locally:

```sh
python -m pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Open `docs/_build/html/index.html`. Internal design notes remain in the repository
and are excluded from the public documentation build.

## Development checkout

When developing alongside the sibling migration repository, install both working
checkouts and the SQL development dependencies:

```sh
pip install -e "../genro-sqlmigration[postgresql,validation]" -e ".[dev]"
```

## License

Apache License 2.0 — Copyright Softwell S.r.l.
