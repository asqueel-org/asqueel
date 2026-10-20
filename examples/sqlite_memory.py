"""A complete SQLite session without configuration or database files.

Run with the experimental branch and its migration extra:
    python examples/sqlite_memory.py
"""
import csv
from io import StringIO

from asqueel import AsqueelDb, SqlDatabaseConfig


def main():
    model = SqlDatabaseConfig()
    root = model.source.db(implementation="sqlite")
    root.connection(name=":memory:", implementation="sqlite")
    product = root.packages().package("shop", sqlschema="shop").table("product", pkey="code")
    product.column("code", size=":10")
    product.column("name", size=":60")

    db = AsqueelDb(model)
    try:
        print(db.migrate().commands)
        products = db.table("shop.product")
        products.insert({"code": "TEA", "name": "Tea"})
        db.commit()
        print(products.query(columns="$code, $name").fetch())
        products.update({"name": "Green tea"}, pkey="TEA")
        db.commit()

        product.column("category", size=":30")
        product.column("stock", dtype="I")
        db.reload_model(model)
        print(db.migrate().commands)
        products = db.table("shop.product")
        products.update({"category": "Drinks", "stock": 8}, pkey="TEA")

        data = StringIO(
            "code,name,category,stock\n"
            "COF,Coffee,Drinks,24\n"
            "MUG,Mug,Kitchen,12\n"
        )
        for row in csv.DictReader(data):
            row["stock"] = int(row["stock"])
            products.insert(row)
        db.commit()
        print(products.query(
            columns="$name, $stock",
            where="$category = :category", category="Drinks",
            order_by="$stock DESC",
        ).fetch())
        db.commit()
        assert db.migration_plan().empty
    finally:
        db.closeConnection()


if __name__ == "__main__":
    main()
