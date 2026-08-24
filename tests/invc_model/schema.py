"""Complete modular invoicing recipe."""

from genro_sql import SqlBuilder

from .tables import customer, invoice, invoice_row


class InvoiceModel(SqlBuilder):
    def main(self, root):
        db = root.db("invoicing")
        schemas = db.schemas()
        invc_schema = schemas.schema("invc", comment="Invoicing")
        tables = invc_schema.tables()
        customer.config_db(tables)
        invoice.config_db(tables)
        invoice_row.config_db(tables)
