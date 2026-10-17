"""Row locking is an explicit plan capability restricted to the root table."""
import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.write_compiler import WriteCompiler


@pytest.fixture
def db():
    config = SqlDatabaseConfig()
    pkg = config.source.db('locking', implementation='postgres').packages().package('app')
    customer = pkg.table('customer', pkey='id')
    customer.column('id')
    customer.column('name')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id')
    invoice.column('customer_id').relation('app.customer.id')
    with build_database(config) as database:
        yield database


@pytest.mark.parametrize('operation', ['insert', 'update', 'delete'])
def test_non_select_lock_is_rejected(db, operation):
    writer = WriteCompiler(db.adapter)
    table = db.table('app.invoice').model
    compiled = getattr(writer, operation)(table, {'id': 1, 'customer_id': 2}, {})
    assert compiled.for_update is False and compiled.lock_table is None
    assert writer.lock_table(table, {}).sql.startswith('LOCK ')
