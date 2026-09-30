"""Explicit table imports; no folder discovery."""
from .customer import CustomerModel
from .product import ProductModel
from .invoice import InvoiceModel
from .invoice_row import InvoiceRowModel


class SalesSchema:
    def configure(self, schemas):
        schema = schemas.schema("sales")
        tables = schema.tables()
        CustomerModel().configure(tables)
        ProductModel().configure(tables)
        InvoiceModel().configure(tables)
        InvoiceRowModel().configure(tables)
        return schema
