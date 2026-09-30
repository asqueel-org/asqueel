"""Two logical schemas using the migration adapter's attached-file layout."""
from genro_bag.resolvers import EnvResolver
from asqueel import SqlDatabaseConfig


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        db = root.db()
        db.connection(name=EnvResolver('ASQUEEL_SQLITE_FILE', default='/tmp/asqueel-example.db'),
                      implementation='sqlite')
        schemas = db.schemas()
        customers = schemas.schema('contacts').tables().table('customer', pkey='id').columns()
        customers.column('id', dtype='I')
        customers.column('name', dtype='T')
        invoices = schemas.schema('sales').tables().table('invoice', pkey='id').columns()
        invoices.column('id', dtype='I')
        invoices.column('customer_id', dtype='I').relation('contacts.customer.id', foreign_key=False)
        invoices.column('description', dtype='T')
