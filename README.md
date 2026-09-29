# Genro SQL

SQL model builder for the Genro framework. It describes databases, schemas,
tables and columns through a
[genro-builders](https://github.com/genropy/genro-builders) dialect and projects
the source tree into the normalized `genro-sqlmigration` structure.

**Status**: Alpha. The model source tree is the single pivot for migration
projection, database inspection and round-tripping back to an editable Python
recipe. Direct DDL rendering remains a reserved placeholder.

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
└── renderer.py       # reserved direct-DDL surface
```

## Supported ecosystem

Python **3.11–3.13**. The verified baseline uses genro-builders **0.27.0**,
genro-bag **0.27.0**, genro-tytx **0.16.0** and genro-toolbox **0.14.0**.
Builders and Bag are direct dependencies because the SQL implementation imports
both APIs. The legacy/modern split has been replaced by the canonical grammar
shown above; it is not reintroduced by this update.

The test profiles additionally verify coinstallation and SQL behavior with
routes **0.30.0** and ASGI **0.46.3**. They do not certify an ASGI server or add
web dependencies to the SQL runtime.

## Development

Use an isolated environment and the complete pinned test profile. The migration
package has no PyPI release, so the profile pins its public Git revision instead
of relying on an arbitrary sibling checkout:

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

Two upstream index regressions remain in the pinned migrator. Their assertions
still execute and are marked **strict expected failures only for that exact Git
revision**. `pytest --runxfail` exposes them as ordinary failures; another
revision or an editable migrator checkout receives no exemption. An unexpected
pass fails CI and requires removing the expectation. See
[delivery status](docs/delivery.md) and [alignment results](docs/ecosystem-alignment.md).

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
