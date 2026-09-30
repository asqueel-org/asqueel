# Asqueel

[![PyPI](https://img.shields.io/pypi/v/asqueel)](https://pypi.org/project/asqueel/)
[![Tests](https://github.com/asqueel-org/asqueel/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/asqueel-org/asqueel/actions/workflows/tests.yml)
[![Codecov](https://codecov.io/gh/asqueel-org/asqueel/branch/main/graph/badge.svg)](https://app.codecov.io/gh/asqueel-org/asqueel)
[![Documentation](https://readthedocs.org/projects/asqueel/badge/?version=latest)](https://asqueel.readthedocs.io/en/latest/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/asqueel-org/asqueel/blob/main/pyproject.toml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](https://github.com/asqueel-org/asqueel/blob/main/LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/asqueel-org/asqueel/main/assets/asqueel/svg/asqueel-wordmark-inverse.svg">
  <img src="https://raw.githubusercontent.com/asqueel-org/asqueel/main/assets/asqueel/svg/asqueel-wordmark-primary.svg" alt="Asqueel" width="360">
</picture>

**Asqueel is a Python database layer that makes your application's data model
reusable across queries, business logic and user interfaces.** Declare tables,
relationships, calculated fields and UI metadata together, then work with that
model through a live `db` object.

It addresses a common source of duplication in database applications: the same
relationship, calculation or field description gets rewritten in queries,
service code and screens. In Asqueel, a related customer name or an invoice
calculation can be defined once as a model column and reused wherever you query
it. UI code can read the field's label and formatting from the same model.
SQL remains available for expressions; Asqueel resolves model names and relation
paths and binds query parameters.

Asqueel brings Genropy's approach to database applications into a standalone
library. The current checkout supports PostgreSQL and SQLite, with explicit writes and transaction
completion. Start with [What is Asqueel?](docs/guide/overview.md)
for the approach and an example. The manual also covers planned capabilities;
[Current status](docs/guide/limitations.md) identifies what works today and what
remains to be implemented.

## Install

```sh
python -m pip install "asqueel[postgresql]"
```

Use `asqueel` for model building and offline compilation only. Add the
`migration` extra to use the separate schema migration integration. From a
checkout, run `python -m pip install -e ".[postgresql]"` in the repository root.

## Build an application database

Declare the model and connection configuration in one recipe:

```python
from asqueel import SqlDatabaseConfig, AsqueelDb


class Shop(SqlDatabaseConfig):
    def main(self, root):
        db = root.db("shop", conninfo="dbname=shop")
        customer = db.schemas().schema("sales").tables().table("customer", pkey="id")
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", x_ui={"label": "Customer name"})


db = AsqueelDb(Shop)
customer = db.table("sales.customer")
query = customer.query(
    columns="$id, $name", where="$id >= :minimum_id",
    params={"minimum_id": 1}, order_by="$id",
)
print(query.sqltext)  # Compiles without opening a connection.
db.close()

```

Against an existing `sales.customer` table, call `query.fetch()` to get a list
of dictionaries. Table writes and reads share a lazy session. Use `db.commit()`
and `db.rollback()`. Select a named connection with `db.tempEnv(connectionName=...)`.
Closing the database rolls back pending work; `with db:` does not commit it.

Construction does not connect or create tables. The
[runnable quickstart](docs/guide/quickstart.md) includes explicit disposable
schema setup and cleanup. [Configuration](docs/guide/configuration.md) explains
layered recipes and live table objects. The separate compiler and low-level
runtime remain available for advanced integrations.

Query expressions are application code; pass external values through parameters
rather than SQL interpolation.

## Configure, migrate and explore a complete example

The [two-schema example](docs/guide/two-schemas.md) separates configuration,
schemas, table declarations and business logic. It includes users/access logs
and customers/products/invoices/rows, with explicit imports and `EnvResolver`
connection settings.

From this source checkout (the CLI is not assumed to be in older PyPI releases):

```sh
python -m pip install -e ".[postgresql,migration]"
asqueel register gestionale ./examples/two_schemas
asqueel check gestionale
asqueel db plan gestionale
asqueel db apply gestionale
asqueel shell gestionale
```

Set the example's `PG*` environment variables for your PostgreSQL server before
`plan`/`apply`; the database account must have the required privileges. `check`
is offline. The registry in `~/.asqueel` stores the folder path, not credentials.
The console provides `db`; the same name works with `AsqueelDb("gestionale")`
in Python. See the [complete walkthrough](docs/guide/two-schemas.md) and
[CLI reference](docs/guide/cli.md) for setup, migrations and transaction behavior.

## Learn and use Asqueel

Start with [What is Asqueel?](docs/guide/overview.md) and
[the object model](docs/guide/concepts.md), run the
[quickstart](docs/guide/quickstart.md), then follow the
[customers and invoices tutorial](docs/guide/tutorial.md). The tutorial includes a
[complete runnable script](docs/guide/_examples/shop_tutorial.py) with assertions,
transaction examples and disposable-schema cleanup.

| You want to… | Read |
|---|---|
| Run the two-schema example, migrate it and open a console | [Complete example](docs/guide/two-schemas.md) and [CLI](docs/guide/cli.md) |
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

For development with the migration integration, install its checkout and Asqueel
with the development dependencies (replace the example path with your checkout):

```sh
pip install -e "../asqueel-migration[postgresql,validation]" -e ".[dev]"
```

## License

Apache License 2.0 — Copyright Softwell S.r.l.

SQLite configuration and runtime limitations are described in the [SQLite guide](docs/guide/sqlite.md).
