"""Complete modular invoicing recipe."""

from asqueel import SqlBuilder

from .tables import customer, invoice, invoice_row


class InvoiceModel(SqlBuilder):
    def main(self, root):
        db = root.db("invoicing")
        schemas = db.packages()
        invc_schema = schemas.package("invc", comment="Invoicing", sqlschema="invc", sqlprefix=False)
        tables = invc_schema.tables()
        customer.config_db(tables)
        invoice.config_db(tables)
        invoice_row.config_db(tables)
