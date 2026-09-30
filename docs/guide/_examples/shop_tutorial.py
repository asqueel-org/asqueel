"""Runnable documentation example; uses and removes its own PostgreSQL schema.

Run with GENRO_SQL_DSN set to a disposable PostgreSQL database connection string.
Only the randomly named genro_tutorial_* schema is created and removed.
"""
# imports-start
import os
from decimal import Decimal
from uuid import uuid4

from genro_sql import CompiledQuery, SqlDatabaseConfig, build_database
# imports-end


# model-start
class Shop(SqlDatabaseConfig):
    def main(self, root):
        tables = root.db("shop").schemas().schema("sales").tables()

        customer = tables.table("customer", pkey="id")
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", notnull=True,
                       x_ui={"label": "Customer name"})

        invoice = tables.table("invoice", pkey="id")
        columns = invoice.columns()
        columns.column("id", dtype="L")
        columns.column("customer_id", dtype="L").relation(
            "sales.customer.id", foreign_key=True, x_name="customer",
        )
        columns.column("total", dtype="N", size="12,2", notnull=True)
        columns.column("note", dtype="T")
        virtuals = invoice.virtual_columns()
        virtuals.aliasColumn("customer_name", relation_path="@customer.name")
        virtuals.formulaColumn("double_total", dtype="N", sql_formula="$total * 2")
        virtuals.formulaColumn("line_total", dtype="N", select=dict(
            table="sales.line", columns="SUM($amount)",
            where="$invoice_id=#THIS.id",
        ))
        virtuals.formulaColumn("has_lines", dtype="B", exists=dict(
            table="sales.line", where="$invoice_id=#THIS.id",
        ))

        columns = tables.table("line", pkey="id").columns()
        columns.column("id", dtype="L")
        columns.column("invoice_id", dtype="L").relation(
            "sales.invoice.id", foreign_key=True, x_name="invoice",
        )
        columns.column("amount", dtype="N", size="12,2")
# model-end


# deployment-start
def open_shop(dsn, physical_schema):
    class Deployment(SqlDatabaseConfig):
        def main(self, root):
            root.db("shop", conninfo=dsn).schemas().schema(
                "sales", x_sql_schema=physical_schema,
            )

    return build_database(Deployment, parents=[Shop])
# deployment-end


# setup-start
def create_tables(db, schema):
    # schema is generated below from uuid4().hex, never supplied by a user.
    for statement in (
        f'CREATE SCHEMA "{schema}"',
        f'CREATE TABLE "{schema}".customer '
        '(id bigint PRIMARY KEY, name text NOT NULL)',
        f'CREATE TABLE "{schema}".invoice '
        f'(id bigint PRIMARY KEY, customer_id bigint REFERENCES "{schema}".customer(id), '
        'total numeric(12,2) NOT NULL, note text)',
        f'CREATE TABLE "{schema}".line '
        f'(id bigint PRIMARY KEY, invoice_id bigint REFERENCES "{schema}".invoice(id), '
        'amount numeric(12,2))',
    ):
        db.execute(CompiledQuery(statement))
    db.commit()
# setup-end


# seed-start
def seed(db):
    customer = db.table("sales.customer")
    customer.insert({"id": 1, "name": "Ada"})
    customer.insert({"id": 2, "name": "Grace"})
    invoice = db.table("sales.invoice")
    invoice.insert({"id": 10, "customer_id": 1, "total": Decimal("125.00"),
                    "note": "First order"})
    invoice.insert({"id": 11, "customer_id": 2, "total": Decimal("40.00"),
                    "note": None})
    line = db.table("sales.line")
    line.insert({"id": 100, "invoice_id": 10, "amount": Decimal("100.00")})
    line.insert({"id": 101, "invoice_id": 10, "amount": Decimal("25.00")})
    db.commit()
# seed-end


# reads-start
def read_invoices(db):
    invoice = db.table("sales.invoice")
    query = invoice.query(
        columns="$id, $customer_name, $total, $line_total, $has_lines",
        order_by="$id",
    )
    assert "SELECT" in query.sqltext  # Compilation performs no I/O.
    rows = query.fetch()
    db.rollback()  # Complete this read-only transaction.
    assert rows == [
        {"id": 10, "customer_name": "Ada", "total": Decimal("125.00"),
         "line_total": Decimal("125.00"), "has_lines": True},
        {"id": 11, "customer_name": "Grace", "total": Decimal("40.00"),
         "line_total": None, "has_lines": False},
    ]
    return rows
# reads-end


# changes-start
def change_customer(db):
    customer = db.table("sales.customer")
    result = customer.update({"id": 1, "name": "Ada Lovelace"}, returning="$id, $name")
    assert result.rows == [{"id": 1, "name": "Ada Lovelace"}]
    assert customer.record(1, mode="dict")["name"] == "Ada Lovelace"
    db.commit()

    try:
        customer.update({"id": 1, "name": "Not saved"})
        raise ValueError("Cancel this unit of work")
    except ValueError:
        db.rollback()

    assert customer.record(1, mode="dict")["name"] == "Ada Lovelace"
    db.rollback()  # Complete the final read-only transaction.
# changes-end


# run-start
def run(dsn):
    schema = "genro_tutorial_" + uuid4().hex
    with open_shop(dsn, schema) as db:
        create_tables(db, schema)
        try:
            seed(db)
            rows = read_invoices(db)
            change_customer(db)
            print(rows)
            print("Tutorial completed; committed writes and rollback verified.")
            return rows
        finally:
            db.rollback()
            db.execute(CompiledQuery(f'DROP SCHEMA "{schema}" CASCADE'))
            db.commit()


if __name__ == "__main__":
    run(os.environ["GENRO_SQL_DSN"])
# run-end
