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

## Development

```bash
pip install -e "../genro-sqlmigration[postgresql,validation]" -e ".[dev]"
pytest tests/
ruff check src/
mypy src/genro_sql
```

The sibling checkout is currently required because `genro-sqlmigration` has
not published the commits used by the inspection and writer regressions. See
the [external delivery gate](docs/delivery.md) for the exact release sequence.

## License

Apache License 2.0 — Copyright 2025 Softwell S.r.l.
