"""Table declaration and its explicitly associated behavior."""
from asqueel import SqlTable


class InvoiceRowLogic(SqlTable):
    """Uses the standard table lifecycle; add domain methods here."""


class InvoiceRowModel:
    def configure(self, tables):
        table = tables.table("invoice_row", pkey="id", x_table_class=InvoiceRowLogic, caption_field="description")
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("invoice_id", dtype="L", notnull=True).relation("sales.invoice.id", foreign_key=True)
        columns.column("product_id", dtype="L", notnull=True).relation("sales.product.id", foreign_key=True)
        columns.column("description", dtype="T", notnull=True)
        columns.column("quantity", dtype="N")
        columns.column("unit_price", dtype="N")
        table.virtual_columns().formulaColumn("amount", sql_formula="$quantity * $unit_price", dtype="N")
        return table
