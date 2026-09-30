"""Table declaration and its explicitly associated behavior."""
from asqueel import SqlTable


class CustomerLogic(SqlTable):
    """Uses the standard table lifecycle; add domain methods here."""


class CustomerModel:
    def configure(self, tables):
        table = tables.table("customer", pkey="id", x_table_class=CustomerLogic, caption_field="name")
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("name", dtype="T", notnull=True)
        columns.column("email", dtype="T")
        return table
