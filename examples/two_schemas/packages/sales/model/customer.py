"""The sales.customer table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("customer", pkey="id", caption_field="name")
        table.column("id", dtype="L", notnull=True)
        table.column("name", dtype="T", notnull=True)
        table.column("email", dtype="T")
