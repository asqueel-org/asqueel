"""The identity.access table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("access", pkey="id")
        table.column("id", dtype="L", notnull=True)
        table.column("user_id", dtype="L", notnull=True).relation("identity.user.id", foreign_key=True)
        table.column("occurred_at", dtype="DHZ")
        table.column("successful", dtype="B")
        table.column("ip_address", dtype="T")
