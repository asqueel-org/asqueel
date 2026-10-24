"""The sales.invoice_row table: its declaration and its behavior."""


class Table:
    def config_db(self, pkg):
        table = pkg.table("invoice_row", pkey="id", caption_field="description")
        table.column("id", dtype="L", notnull=True)
        table.column("invoice_id", dtype="L", notnull=True).relation("sales.invoice.id", foreign_key=True)
        table.column("product_id", dtype="L", notnull=True).relation("sales.product.id", foreign_key=True)
        table.column("description", dtype="T", notnull=True)
        table.column("quantity", dtype="N")
        table.column("unit_price", dtype="N")
        table.formulaColumn("amount", sql_formula="$quantity * $unit_price", dtype="N")
