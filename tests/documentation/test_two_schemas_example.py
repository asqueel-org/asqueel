"""The composed example resolves cross-schema paths without database I/O."""
from asqueel import build_database
from examples.two_schemas.configure import DatabaseConfiguration
from examples.two_schemas.schemas.sales.invoice_logic import InvoiceLogic


def test_explicit_schema_example_builds_and_compiles_offline(monkeypatch):
    import psycopg

    def forbidden(*args, **kwargs):
        raise AssertionError('Configuration and compilation must not connect')

    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setenv('PGPORT', '5432')
    monkeypatch.setenv('PGDATABASE', 'example_test')
    with build_database(DatabaseConfiguration) as db:
        for name in ('identity.user', 'identity.access', 'sales.customer',
                     'sales.product', 'sales.invoice', 'sales.invoice_row'):
            assert db.table(name).model.pkey == ('id',)
        assert db.config('connection.name') == 'example_test'
        invoice = db.table('sales.invoice')
        assert isinstance(invoice, InvoiceLogic)
        query = invoice.query(
            columns='$number, @customer_id.name AS customer, @created_by.username AS author',
            where='$customer_id = :customer_id', params={'customer_id': 42},
        ).compiled
        assert 'JOIN "sales"."customer"' in query.sql
        assert 'JOIN "identity"."user"' in query.sql
        assert query.params == {'customer_id': 42}
        rows = invoice.rows_query(100).compiled
        assert '"quantity" * ' in rows.sql
        assert rows.params == {'invoice_id': 100}
        access = db.table('identity.access').query(
            columns='@user_id.username',
        ).compiled
        assert 'JOIN "identity"."user"' in access.sql
        product = db.table('sales.invoice_row').query(
            columns='@product_id.code, @invoice_id.number',
        ).compiled
        assert 'JOIN "sales"."product"' in product.sql
        assert 'JOIN "sales"."invoice"' in product.sql
