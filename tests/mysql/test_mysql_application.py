"""Public application API against MySQL: migration, write cycle, queries."""
from decimal import Decimal

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, UnsupportedFeatureError

pytestmark = pytest.mark.mysql


@pytest.fixture
def application(mysql_server):
    params, prefix = mysql_server
    schema = prefix + '_app'

    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            tables = root.db('acceptance', implementation='mysql', connect_kwargs=params).packages().package(
                'app', sqlschema=schema, sqlprefix=False).tables()
            customer = tables.table('customer', pkey='id').columns()
            customer.column('id', dtype='I')
            customer.column('name', dtype='A', size=':40', notnull=True)
            customer.column('active', dtype='B')
            invoice = tables.table('invoice', pkey='id').columns()
            invoice.column('id', dtype='I')
            invoice.column('customer_id', dtype='I').relation('app.customer.id', foreign_key=True)
            invoice.column('total', dtype='N', size='10,2')
            ticket = tables.table('ticket', pkey='id').columns()
            ticket.column('id', dtype='serial')
            ticket.column('note', dtype='T')

    db = AsqueelDb(Recipe).session()
    try:
        db.migrate()
        db.commit()
        yield db
    finally:
        db.shared.close()


def test_migration_is_complete(application):
    assert application.migration_plan()['empty']


def test_write_cycle_and_queries(application):
    db = application
    customer, invoice = db.table('app.customer'), db.table('app.invoice')
    customer.insert({'id': 1, 'name': 'Rossi', 'active': True})
    customer.insert({'id': 2, 'name': 'Bianchi', 'active': False})
    invoice.insert({'id': 10, 'customer_id': 1, 'total': Decimal('12.50')})
    invoice.insert({'id': 11, 'customer_id': 1, 'total': Decimal('7.50')})
    db.commit()
    rows = invoice.query('$id, @customer_id.name AS customer, $total', where='@customer_id.active IS TRUE',
                         order_by='$id').fetch()
    assert [dict(row) for row in rows] == [
        {'id': 10, 'customer': 'Rossi', 'total': Decimal('12.50')},
        {'id': 11, 'customer': 'Rossi', 'total': Decimal('7.50')}]
    assert [dict(row) for row in customer.query('$name', where='$name ILIKE :n', sqlparams={'n': 'b%'}).fetch()] == [
        {'name': 'Bianchi'}]
    assert [dict(row) for row in customer.query('$id', order_by='$id', limit=1, offset=1).fetch()] == [{'id': 2}]
    record = dict(customer.query('*', where='$id=2').fetchRecord())
    assert record['active'] is False
    customer.update({'id': 2, 'name': 'Verdi', 'active': True}, old_record=record)
    invoice.delete({'id': 11})
    db.commit()
    assert [dict(row) for row in customer.query('$name', order_by='$id').fetch()] == [
        {'name': 'Rossi'}, {'name': 'Verdi'}]
    assert [dict(row) for row in invoice.query('$id').fetch()] == [{'id': 10}]


def test_for_update_query(application):
    customer = application.table('app.customer')
    customer.insert({'id': 1, 'name': 'Rossi'})
    application.commit()
    assert [dict(row) for row in customer.query('$name', for_update=True).fetch()] == [{'name': 'Rossi'}]
    application.rollback()


def test_vacuum_runs_on_a_separate_connection(application):
    application.table('app.customer').insert({'id': 1, 'name': 'Rossi'})
    application.commit()
    application.vacuum()
    application.vacuum('"' + application.table('app.customer').model.sqlschema + '"."customer"')
    assert [dict(row) for row in application.table('app.customer').query('$name').fetch()] == [{'name': 'Rossi'}]


def test_table_lock_is_refused(application):
    with pytest.raises(UnsupportedFeatureError, match='table locks'):
        application.table('app.customer').lock()


@pytest.mark.xfail(strict=True, reason='asqueel#58: UPDATE/DELETE of a query selection reads the same table '
                                       '(MySQL error 1093); MySQL needs its own write compiler')
def test_selection_update_and_delete(application):
    customer = application.table('app.customer')
    customer.insert({'id': 1, 'name': 'Rossi'})
    with pytest.raises(UnsupportedFeatureError):
        customer.query(where='$id=1').sql_update({'name': 'Verdi'})


@pytest.mark.xfail(strict=True, reason='asqueel#21: without RETURNING the serial key the database decides '
                                       'is not written back, and nothing refuses the write')
def test_serial_insert_is_refused(application):
    with pytest.raises(UnsupportedFeatureError):
        application.table('app.ticket').insert({'note': 'x'})
