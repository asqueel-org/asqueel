# Installation

Asqueel requires Python 3.11 or later. The supported Python test matrix is
3.11–3.13. PostgreSQL and SQLite are implemented execution backends. SQLite uses the standard library and requires SQLite 3.35 or later.
The package is alpha; check the API and feature limits when upgrading.

## Choose the dependencies you need

For a PostgreSQL application:

```sh
python -m pip install "asqueel[postgresql]"
```

This includes psycopg 3 and its binary distribution. The application supplies a
PostgreSQL connection string; Asqueel does not install or start a database.

For model definitions, query compilation, or generating Python recipes without
executing queries:

```sh
python -m pip install asqueel
```

The core depends on genro-builders and genro-bag. It does not require psycopg
or the migration engine. PostgreSQL query compilation is available without the
client library because it does not perform I/O.

For the bridge to the separate migration engine, add the migration extra:

```sh
python -m pip install "asqueel[postgresql,migration]"
```

See [migrations](migrations.md) before using a model to plan schema changes.
Declaring a model or creating a compiler never creates tables automatically.

## Working from a checkout

To use the code checked out from Git, install from the repository root:

```sh
python -m pip install -e ".[postgresql]"
```

Use the documentation built for the same version as your installation.

To read these guides locally, install the documentation extra and build HTML:

```sh
python -m pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Open `docs/_build/html/index.html`. No PostgreSQL connection is needed to build
the documentation. Next, run the [quickstart](quickstart.md).
