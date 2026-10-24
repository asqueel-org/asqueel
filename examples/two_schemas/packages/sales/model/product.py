"""The sales.product table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("product", pkey="id", caption_field="description")
        table.column("id", dtype="L", notnull=True)
        table.column("code", dtype="T", unique=True)
        table.column("description", dtype="T", notnull=True)
        table.column("unit_price", dtype="N")
