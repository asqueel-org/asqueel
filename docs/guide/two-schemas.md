# A database with two explicitly imported schemas

The repository's `examples/two_schemas` folder is a complete configuration
example. It uses the current grammar and runtime, with no folder discovery or
package loader. It includes six tables:

| Schema | Tables | Purpose |
|---|---|---|
| `identity` | `user`, `access` | Users and their access log |
| `sales` | `customer`, `product`, `invoice`, `invoice_row` | Customers, products, invoices and rows |

An invoice references both its customer in `sales` and its author in `identity`.
Invoice rows reference an invoice and a product; `amount` is a query-time SQL
formula. This illustrates composition and relations, not a complete accounting
or authentication application.

## Files and explicit composition

```text
examples/two_schemas/
├── configure.py
├── __main__.py
└── schemas/
    ├── identity/
    │   ├── schema.py
    │   ├── user.py
    │   └── access.py
    └── sales/
        ├── schema.py
        ├── customer.py
        ├── product.py
        ├── invoice.py
        ├── invoice_logic.py
        └── invoice_row.py
```

The configuration calls its sections in order: declare the DB connection, then
import the schemas. This is the actual example source:

```{literalinclude} ../../examples/two_schemas/configure.py
:language: python
```

`EnvResolver` is read through the standard configuration handler. The symbolic
registration name below is independent of `connection.name`, which names the
physical PostgreSQL database. Each schema explicitly imports its tables:

```{literalinclude} ../../examples/two_schemas/schemas/sales/schema.py
:language: python
```

The `Model` class declares the table and links its `Logic` class using
`x_table_class`. These are ordinary Python classes and example conventions;
there is no new mandatory `SqlTableModel` base class. The two classes may share
a module, as in `customer.py`, or live in separate modules, as for invoices:

```{literalinclude} ../../examples/two_schemas/schemas/sales/invoice.py
:language: python
```

```{literalinclude} ../../examples/two_schemas/schemas/sales/invoice_logic.py
:language: python
```

The resulting object is still a single table handle:
`db.table("sales.invoice")`. It exposes both query/write operations and the
custom `rows_query()` method.

## Install and inspect without connecting

These instructions target the source checkout, including its new CLI; they do
not assume an older PyPI release contains it. From the repository root:

```sh
python -m pip install -e ".[postgresql,migration]"
python -m examples.two_schemas
asqueel register gestionale ./examples/two_schemas
asqueel check gestionale
```

The module command prints compiled SQL and bound parameters without executing
queries. `register` stores the absolute folder path under
`~/.asqueel/databases/gestionale.json`; `check` validates the configuration
without contacting PostgreSQL. The name can then be used from another working
directory. Set `ASQUEEL_HOME` to use a different local registry.

## Create the physical database

Use an existing PostgreSQL server and account. For example, select a disposable
physical database while keeping the registered alias `gestionale`:

```sh
export PGHOST=localhost
export PGPORT=5432
export PGUSER=app
export PGDATABASE=asqueel_demo
asqueel db plan gestionale
asqueel db apply gestionale
asqueel db plan gestionale
```

The account must already exist and have permission to create the database and
its objects. The recipe reads `PGPASSWORD` if provided; otherwise the driver's
normal authentication, such as `.pgpass`, remains available. No credential is
stored in the registration card.

`plan` only displays SQL. `apply` uses Asqueel Migration to create a missing DB,
both schemas, all six tables and their supported constraints/indexes. It then
checks again using a fresh comparison. For this fresh example, the final plan
reports `No changes.` The formula column is not a stored physical column.
See [migration command semantics](cli.md#inspect-and-apply-migrations) for
existing databases, removal policy and partial failures.

## Read and write from Python

After applying the structure, run this once on the fresh example database:

```python
from decimal import Decimal
from asqueel import build_database

with build_database("gestionale") as db:
    db.table("identity.user").insert({"id": 1, "username": "ada"})
    db.table("identity.access").insert({"id": 1, "user_id": 1, "successful": True})
    db.table("sales.customer").insert({"id": 1, "name": "Ada"})
    db.table("sales.product").insert({"id": 1, "code": "P1", "description": "Widget"})
    db.table("sales.invoice").insert({
        "id": 1, "number": "INV-1", "customer_id": 1, "created_by": 1,
    })
    db.table("sales.invoice_row").insert({
        "id": 1, "invoice_id": 1, "product_id": 1, "description": "Widget",
        "quantity": Decimal("2"), "unit_price": Decimal("12.50"),
    })
    db.commit()

    invoice = db.table("sales.invoice").query(
        columns="$number, @customer_id.name AS customer, @created_by.username AS author",
    ).fetch()[0]
    assert invoice["customer"] == "Ada"
    assert invoice["author"] == "ada"
    assert db.table("sales.invoice").rows_query(1).fetch()[0]["amount"] == Decimal("25")
```

The example supplies integer IDs explicitly. Repeating those inserts in the
same database will violate primary keys; it is not a seed/upsert command.

## Use the console

```sh
asqueel shell gestionale
```

`db` is already available:

```python
rows = db.table("sales.invoice").rows_query(1).fetch()
print(rows)
db.table("sales.customer").insert({"id": 2, "name": "Grace"})
db.commit()
```

Use `db.rollback()` to discard pending changes. Leaving the console closes the
DB and rolls back uncommitted work. `asqueel unregister gestionale` only removes
the local alias; it does not drop the database or delete the example folder.
