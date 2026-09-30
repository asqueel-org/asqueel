"""Table declaration and its explicitly associated behavior."""
from asqueel import SqlTable


class UserLogic(SqlTable):
    """Uses the standard table lifecycle; add domain methods here."""


class UserModel:
    def configure(self, tables):
        table = tables.table("user", pkey="id", x_table_class=UserLogic, caption_field="username")
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("username", dtype="T", notnull=True, unique=True)
        columns.column("email", dtype="T")
        columns.column("active", dtype="B")
        return table
