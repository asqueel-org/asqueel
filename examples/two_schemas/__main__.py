"""Run from the repository root: python -m examples.two_schemas."""
from asqueel import AsqueelDb

from .configure import DatabaseConfiguration


def main():
    db = AsqueelDb(DatabaseConfiguration)
    try:
        for name in ("identity.user", "identity.access", "sales.customer",
                     "sales.product", "sales.invoice", "sales.invoice_row"):
            print(name)
        query = db.table("sales.invoice").query(
            columns="$number, @customer_id.name AS customer, @created_by.username AS author",
            where="$customer_id = :customer_id", params={"customer_id": 42},
        ).compiled
        print(query.sql)
        print(query.params)
        rows = db.table("sales.invoice").rows_query(100).compiled
        print(rows.sql)
        print(rows.params)
    finally:
        db.close()


if __name__ == "__main__":
    main()
