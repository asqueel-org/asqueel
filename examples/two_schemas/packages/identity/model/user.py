"""The identity.user table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("user", pkey="id", caption_field="username")
        table.column("id", dtype="L", notnull=True)
        table.column("username", dtype="T", notnull=True, unique=True)
        table.column("email", dtype="T")
        table.column("active", dtype="B")
