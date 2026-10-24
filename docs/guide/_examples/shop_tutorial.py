"""Runnable documentation example on PostgreSQL or SQLite.

With ASQUEEL_DSN set to a disposable PostgreSQL database connection string, it
creates and removes a randomly named genro_tutorial_* schema. Without it, it
uses a SQLite file in a temporary directory and removes the directory.
"""
# imports-start
import os
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from asqueel import CompiledQuery, SqlDatabaseConfig, AsqueelDb
# imports-end


# model-start
class Shop(SqlDatabaseConfig):
    def main(self, root):
        tables = root.db("shop").packages().package("sales", sqlschema="sales", sqlprefix=False).tables()
        self.customer(tables)
        self.invoice(tables)
        self.line(tables)

    def customer(self, tables):
        customer = tables.table("customer", pkey="id")
        columns = customer.columns()
        columns.column("id", dtype="L")
        columns.column("name", dtype="T", notnull=True)

    def invoice(self, tables):
        invoice = tables.table("invoice", pkey="id")
        columns = invoice.columns()
        columns.column("id", dtype="L")
        columns.column("customer_id", dtype="L").relation(
            "sales.customer.id", foreign_key=True, relation_name="invoices",
        )
        columns.column("total", dtype="N", size="12,2", notnull=True)
        columns.column("note", dtype="T")
        virtuals = invoice.virtual_columns()
        virtuals.formulaColumn("double_total", dtype="N", sql_formula="$total * 2")
        virtuals.formulaColumn("line_total", dtype="N", select=dict(
            table="sales.line", columns="SUM($amount)",
            where="$invoice_id=#THIS.id",
        ))
        virtuals.formulaColumn("has_lines", dtype="B", exists=dict(
            table="sales.line", where="$invoice_id=#THIS.id",
        ))

    def line(self, tables):
        columns = tables.table("line", pkey="id").columns()
        columns.column("id", dtype="L")
        columns.column("invoice_id", dtype="L").relation(
            "sales.invoice.id", foreign_key=True, relation_name="lines",
        )
        columns.column("amount", dtype="N", size="12,2")
# model-end


# deployment-start
def open_shop(dsn, physical_schema):
    class Deployment(SqlDatabaseConfig):
        def main(self, root):
            root.db("shop", implementation="postgres", conninfo=dsn).packages().package(
                "sales", sqlschema=physical_schema, sqlprefix=False
            )

    return AsqueelDb(Deployment, parents=[Shop])


def open_sqlite_shop(path):
    class Deployment(SqlDatabaseConfig):
        def main(self, root):
            root.db("shop").connection(name=str(path), implementation="sqlite")

    return AsqueelDb(Deployment, parents=[Shop])
# deployment-end


# setup-start
def create_tables(db):
    # The migration creates the schemas and tables the model declares.
    db.migrate()
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
        columns="$id, @customer_id.name AS customer_name, $total, $double_total, "
                "$line_total, $has_lines",
        order_by="$id",
    )
    assert "SELECT" in query.sqltext  # Compilation performs no I/O.
    rows = query.fetch()
    db.rollback()  # Complete this read-only transaction.
    assert [dict(row) for row in rows] == [
        {"id": 10, "customer_name": "Ada", "total": Decimal("125.00"),
         "double_total": Decimal("250.00"), "line_total": Decimal("125.00"),
         "has_lines": True},
        {"id": 11, "customer_name": "Grace", "total": Decimal("40.00"),
         "double_total": Decimal("80.00"), "line_total": None, "has_lines": False},
    ]
    return rows


def read_customers(db):
    customer = db.table("sales.customer")
    rows = customer.query(
        columns="$id, $name, @invoices.aggr(count() AS invoices, sum($total) AS amount)",
        order_by="$id",
    ).fetch()
    db.rollback()
    assert [dict(row) for row in rows] == [
        {"id": 1, "name": "Ada", "invoices": 1, "amount": Decimal("125.00")},
        {"id": 2, "name": "Grace", "invoices": 1, "amount": Decimal("40.00")},
    ]
    return rows
# reads-end


# changes-start
def change_customer(db):
    customer = db.table("sales.customer")
    result = customer.update({"id": 1, "name": "Ada Lovelace"})
    assert result == {"id": 1, "name": "Ada Lovelace"}
    assert customer.query(where="$id = :id", id=1).fetchRecord()["name"] == "Ada Lovelace"
    db.commit()

    try:
        customer.update({"id": 1, "name": "Not saved"})
        raise ValueError("Cancel this unit of work")
    except ValueError:
        db.rollback()

    assert customer.query(where="$id = :id", id=1).fetchRecord()["name"] == "Ada Lovelace"
    db.rollback()  # Complete this read-only transaction.


def remove_line(db):
    db.table("sales.line").delete({"id": 101})
    db.commit()
    rows = db.table("sales.invoice").query(
        columns="$id, $line_total", where="$id = :id", id=10,
    ).fetch()
    db.rollback()  # Complete the final read-only transaction.
    assert [dict(row) for row in rows] == [{"id": 10, "line_total": Decimal("100.00")}]
# changes-end


# run-start
def run_flow(db):
    create_tables(db)
    seed(db)
    rows = read_invoices(db)
    read_customers(db)
    change_customer(db)
    remove_line(db)
    print(rows)
    print("Tutorial completed; committed writes and rollback verified.")
    return rows


def run(dsn=None):
    if dsn is None:
        with TemporaryDirectory() as folder:
            db = open_sqlite_shop(Path(folder) / "shop.db")
            try:
                return run_flow(db)
            finally:
                db.closeConnection()
    schema = "genro_tutorial_" + uuid4().hex
    db = open_shop(dsn, schema)
    try:
        try:
            return run_flow(db)
        finally:
            db.rollback()
            # schema is generated above from uuid4().hex, never supplied by a user.
            db.execute(CompiledQuery(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            db.commit()
    finally:
        db.closeConnection()


if __name__ == "__main__":
    run(os.environ.get("ASQUEEL_DSN"))
# run-end
