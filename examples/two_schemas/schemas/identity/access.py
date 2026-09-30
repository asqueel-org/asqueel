"""Table declaration and its explicitly associated behavior."""
from asqueel import SqlTable


class AccessLogic(SqlTable):
    """Uses the standard table lifecycle; add domain methods here."""


class AccessModel:
    def configure(self, tables):
        table = tables.table("access", pkey="id", x_table_class=AccessLogic)
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("user_id", dtype="L", notnull=True).relation("identity.user.id", foreign_key=True)
        columns.column("occurred_at", dtype="DHZ")
        columns.column("successful", dtype="B")
        columns.column("ip_address", dtype="T")
        return table
