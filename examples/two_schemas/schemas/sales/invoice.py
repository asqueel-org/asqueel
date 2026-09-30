"""Table declaration and its explicitly associated behavior."""
from .invoice_logic import InvoiceLogic


class InvoiceModel:
    def configure(self, tables):
        table = tables.table("invoice", pkey="id", x_table_class=InvoiceLogic, caption_field="number")
        columns = table.columns()
        columns.column("id", dtype="L", notnull=True)
        columns.column("number", dtype="T", notnull=True)
        columns.column("issued_on", dtype="D")
        columns.column("customer_id", dtype="L", notnull=True).relation("sales.customer.id", foreign_key=True)
        columns.column("created_by", dtype="L", notnull=True).relation("identity.user.id", foreign_key=True)
        return table
