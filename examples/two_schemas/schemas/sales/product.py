"""Table declaration and its explicitly associated behavior."""
from asqueel import SqlTable


class ProductLogic(SqlTable):
    """Uses the standard table lifecycle; add domain methods here."""


class ProductModel:
    def configure(self, tables):
        table = tables.table("product", pkey="id", x_table_class=ProductLogic, caption_field="description")
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("code", dtype="T", unique=True)
        columns.column("description", dtype="T", notnull=True)
        columns.column("unit_price", dtype="N")
        return table
