# Genro SQL

SQL model builder for the Genro framework. It describes databases, schemas,
tables and columns through a
[genro-builders](https://github.com/genropy/genro-builders) dialect and projects
the source tree into the normalized `genro-sqlmigration` structure.

**Status**: Alpha. The native PostgreSQL profile adds a resolved model, query
compiler, read-only catalog import and an awaitable runtime using dedicated
threads. It targets new applications. Legacy application compatibility and
advanced Genro semantics remain later milestones. Direct DDL rendering remains
a reserved placeholder; physical migration uses `genro-sqlmigration`.

Install the PostgreSQL runtime with `pip install "genro-sql[postgresql]"`.
The model and compiler work without a database driver. Migration is a separate
optional extra: `genro-sql[migration]`.

```python
from genro_sql import PostgresCompiler, PostgresDatabase, resolve_model

# builder is a built SqlBuilder recipe; SQL fragments are trusted application code.
compiler = PostgresCompiler(resolve_model(builder))
query = compiler.select("invc.invoice", columns="$id, $total",
                        where="$total >= :minimum", params={"minimum": 100})

async def read_invoices(conninfo):
    async with PostgresDatabase(conninfo, max_workers=4, max_pending=16) as db:
        async with db.transaction() as tx:
            result = await tx.execute(query)
            return result.rows
```

A transaction pins one connection to one worker. PostgreSQL I/O, materialization,
commit, rollback and close happen off the event loop. Cancellation waits for
ongoing synchronous work and cleanup; it does not instantly stop the server query.
Use PostgreSQL timeouts for bounded server execution. Thread count and admission
queue are bounded; connections are fresh per transaction, not persistently pooled.

See [native model](docs/native-model.md), [compiler](docs/native-compiler.md),
[runtime](docs/native-runtime.md), [V1 verification](docs/native-v1-delivery.md)
and [version roadmap](docs/design/07-release-proposal.md).
`aggregateRows` is explicitly unsupported in every native entry point.

The [data adapter architecture](docs/data-adapters-delivery.md) separates
`QueryCompiler` (resolved plans), `PostgresDialect` (SQL), `PsycopgDriver`
(binding and client calls), and `ThreadedDatabase` (session lifecycle).
The PostgreSQL classes shown above remain convenience facades. Structural
catalog providers and the adapters in sqlmigration remain separate from
data execution; only PostgreSQL data execution is currently implemented.

Repeated structure is explicit in the authoring grammar:

```python
db = root.db("billing")
schemas = db.schemas()
invc = schemas.schema("invc")
tables = invc.tables()
invoice = tables.table("invoice", pkey="id")
columns = invoice.columns()
customer_id = columns.column("customer_id", dtype="L")
customer_id.relation("invc.customer.id", foreign_key=True)
```

The source relation belongs to its column. The migration renderer projects the
same physical foreign key under the table's normalized JSON `relations` map.

## Layout

```
src/genro_sql/
├── builder.py        # SqlBuilder and source-path rules
├── elements.py       # canonical explicit grammar
├── migration.py      # source tree to normalized migration JSON
├── reader.py         # normalized migration JSON to source tree
├── emitter.py        # source tree to an importable Python recipe
├── contracts.py      # native model, compiled query and result contracts
├── model.py          # logical/physical naming and UI resolution
├── compiler.py       # common query planner and PostgreSQL facade
├── query_plan.py     # resolved plans and structured SQL fragments
├── dialects/         # data SQL dialects, independent of drivers
├── drivers/          # binding and optional DB client implementations
├── runtime.py        # awaitable transaction-pinned thread execution
├── catalog_provider.py # structural introspection boundary
├── importers.py      # read-only PostgreSQL catalog import
├── projection.py     # resolved physical model to migration grammar
└── renderer.py       # reserved direct-DDL surface
```

## Supported ecosystem

Python **3.11–3.13**. The verified baseline uses genro-builders **0.27.0**,
genro-bag **0.27.0**, genro-tytx **0.16.0** and genro-toolbox **0.14.0**.
Builders and Bag are direct dependencies because the SQL implementation imports
both APIs. The legacy/modern split has been replaced by the canonical grammar
shown above; it is not reintroduced by this update.

The test profiles additionally verify coinstallation and SQL behavior with
routes **0.30.1** and ASGI **0.46.3**. They do not certify an ASGI server or add
web dependencies to the SQL runtime.

## Development

Use an isolated environment and the complete pinned test profile. It uses the
published `genro-sqlmigration` 0.1.0 release and psycopg 3.3.6, without relying
on a sibling checkout:

```bash
python3.12 -m venv venv
. venv/bin/activate
python -m pip install -r requirements/core.txt
python -m pip install --no-deps --no-build-isolation -e .
pytest -m "not postgresql" -ra
ruff check src tests scripts
mypy src/genro_sql
```

`requirements/routes.txt` and `requirements/asgi.txt` add the ecosystem profiles.
Regenerate a profile deliberately, for example:

```bash
uv pip compile requirements/core.in --universal --python-version 3.11 --output-file requirements/core.txt
```

The current published migrator passes the former index-name/DESC and identifier
quoting regression tests. Their assertions run normally; historical expected
failure markers have been removed. Earlier results remain recorded in
[alignment history](docs/ecosystem-alignment.md).

For a local migration checkout carrying the missing upstream fixes, the original
development command remains available:

```bash
pip install -e "../genro-sqlmigration[postgresql,validation]" -e ".[dev]"
```

PostgreSQL tests create and drop dedicated `test_genro_sql_*` databases. Run them
only against a disposable server via `GNR_TEST_PG_HOST`, `GNR_TEST_PG_PORT`,
`GNR_TEST_PG_USER` and `GNR_TEST_PG_PASSWORD`. CI provides its own PostgreSQL 17
service.

## Distribution verification

```bash
python -m build --no-isolation
python -m pip install --no-deps --force-reinstall dist/*.whl
python -m pip check
python scripts/check_installed.py
```

Use a fresh environment for wheel verification. The script checks import origins,
`py.typed` and the packaged grammar reference, then runs the suite outside the
checkout. Add `--postgresql` for the dedicated database integration tests.
`--core-only` verifies model construction, validation and Python emission in an
environment where the optional migrator is absent.

CI covers Python 3.11–3.13, the routes/ASGI profiles, PostgreSQL and a separate
core-only install with the newest allowed dependencies.

## License

Apache License 2.0 — Copyright 2025 Softwell S.r.l.
