"""Behavior may live separately from the declaration."""
from asqueel import SqlTable


class InvoiceLogic(SqlTable):
    def rows_query(self, invoice_id):
        """Return a parameterized query; execution remains the caller's choice."""
        return self.db.table("sales.invoice_row").query(
            columns="$id, $description, $quantity, $unit_price, $amount",
            where="$invoice_id = :invoice_id", invoice_id=invoice_id,
            order_by="$id",
        )
