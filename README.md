# Genro SQL

Define SQL models in Python, compile parameterized queries, and work with
PostgreSQL through a synchronous API. Genro SQL keeps logical names, physical
database names, relationships, and column UI metadata in a shared model.

**Status: alpha.** Python 3.11–3.13 is tested. PostgreSQL is the supported
execution backend. The runtime uses the calling thread; there is no async API.

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
rather than SQL interpolation. This native profile returns dictionaries; legacy
Selection/Bag output is not implemented.

## Application developer guides

- [Installation](docs/guide/installation.md) and [quickstart](docs/guide/quickstart.md)
- [Configuration and application objects](docs/guide/configuration.md)
- [Models, relationships, naming and UI metadata](docs/guide/models.md)
- [Queries, formulas and writes](docs/guide/queries.md)
- [Transactions and error handling](docs/guide/transactions.md)
- [Environment scopes](docs/guide/environment.md)
- [Partitions, drafts and soft deletion](docs/guide/row-policies.md)
- [Importing an existing database](docs/guide/importing.md)
- [Schema migration integration](docs/guide/migrations.md)
- [Using adapters](docs/guide/adapters.md) and [supported features](docs/guide/limitations.md)

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
