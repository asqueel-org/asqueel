# Database configuration with two package folders

A runnable example using the current Asqueel API. `configure.py` declares two
packages, each with the path of its folder in the package layout: `main.py`
holds class `Package`, `model/<table>.py` holds class `Table`.

```text
two_schemas/
├── configure.py                 # DB settings and the two package declarations
├── __main__.py                  # Offline query compilation demo
└── packages/
    ├── identity/
    │   ├── main.py              # Package
    │   └── model/
    │       ├── access.py        # Table: identity.access
    │       └── user.py          # Table: identity.user
    └── sales/
        ├── main.py              # Package
        └── model/
            ├── customer.py      # Table: sales.customer
            ├── invoice.py       # Table: sales.invoice, with rows_query()
            ├── invoice_row.py   # Table: sales.invoice_row
            └── product.py       # Table: sales.product
```

`DatabaseConfiguration.main()` calls `database_section()` then
`packages_section()`, which declares
`package(name, path=..., sqlschema=name, sqlprefix=False)` for `identity` and
`sales`. Each `Table.config_db(self, pkg)` declares its table on the package;
the package runs the modules in alphabetical order. The `Table` class, combined
with `SqlTable`, is the runtime class of the table: the sales `invoice` module
adds `rows_query(invoice_id)` to illustrate a custom table method. The other
tables keep Asqueel's standard behavior.

## Model

- `identity.user`: username, email, active flag.
- `identity.access`: user, timestamp, outcome, IP address. This is an access log,
  not an authentication or permission implementation.
- `sales.customer`: name and email.
- `sales.product`: code, description and price.
- `sales.invoice`: number, date, customer and author from `identity.user`.
- `sales.invoice_row`: invoice, product, description, quantity and captured unit
  price; `amount` is a SQL formula (`quantity * unit_price`).

Relations declare physical foreign keys as well as navigable paths. IDs are
explicit integer keys supplied by the caller. Invoice arithmetic is illustrative;
VAT, rounding, numbering and document lifecycle are outside this example.

## Run without PostgreSQL

From the repository root, with the project's dependencies installed:

```sh
PYTHONPATH=src python -m examples.two_schemas
```

This builds and validates the composed model, then prints parameterized SQL for
invoices with customer/author joins and invoice rows with their calculated amount.
It does not connect, execute queries, create tables or apply migrations.

## Connection settings

`database_section()` creates a DB node and its single `connection` section.
`connection.name` is the physical database name, not a connection label. Each
field uses the standard `EnvResolver`: `PGHOST`, `PGPORT`, `PGDATABASE`,
`PGUSER`, and optionally `PGPASSWORD`. Defaults are `localhost`, `5432`,
`two_schemas`, and `app`. Passwords are not embedded or printed. The handler
resolves attributes when reading configuration; credentials do not belong to
the package folders.

## Register, migrate and open a console

With `asqueel[postgresql,migration]` installed, from the repository root:

```sh
asqueel register gestionale ./examples/two_schemas
asqueel check gestionale
asqueel db plan gestionale
asqueel db apply gestionale
asqueel shell gestionale
```

The plan/apply commands connect to PostgreSQL. The migrator creates a missing
DB (if the account has permission), schemas, tables and constraints. Apply
verifies a fresh comparison afterward. Removals are disabled unless explicitly
enabled with `--allow-removals`. Set the `PG*` variables for the intended server.
The alias is stored in `~/.asqueel/databases/gestionale.json`; its card contains
only the absolute folder path. `ASQUEEL_HOME` can select another registry.

In the console, `db` is already available. Call `db.commit()` to save writes;
uncommitted changes are rolled back on exit. The same name works in Python:

```python
from asqueel import AsqueelDb

db = AsqueelDb("gestionale")
rows = db.table("sales.customer").query().fetch()
db.closeConnection()

```

The same configuration can be used by an application:

```python
from asqueel import AsqueelDb
from examples.two_schemas.configure import DatabaseConfiguration

db = AsqueelDb(DatabaseConfiguration)
query = db.table("sales.invoice").rows_query(100)
print(query.compiled.sql)  # No connection
# rows = query.fetch()     # Requires an existing matching PostgreSQL schema
db.closeConnection()

```

Deployment customization can also use the existing `AsqueelDb(...,
parents=[...])` configuration layers. The package folders do not own
credentials or connections.
