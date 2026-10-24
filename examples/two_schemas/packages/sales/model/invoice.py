"""The sales.invoice table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("invoice", pkey="id", caption_field="number")
        table.column("id", dtype="L", notnull=True)
        table.column("number", dtype="T", notnull=True)
        table.column("issued_on", dtype="D")
        table.column("customer_id", dtype="L", notnull=True).relation("sales.customer.id", foreign_key=True)
        table.column("created_by", dtype="L", notnull=True).relation("identity.user.id", foreign_key=True)

    def rows_query(self, invoice_id):
        """Return a parameterized query; execution remains the caller's choice."""
        return self.db.table("sales.invoice_row").query(
            columns="$id, $description, $quantity, $unit_price, $amount",
            where="$invoice_id = :invoice_id", invoice_id=invoice_id,
            order_by="$id",
        )
