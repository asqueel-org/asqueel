"""Independent SQL execution on temporary tables; compilation cannot do I/O."""
import sqlite3

import psycopg
import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from tests.native_support import postgres_dsn

# Deliberately inserted out of order; customer 2 has no invoices, customer 3
# has one invoice whose code is NULL. Those are different join/count cases.
INVOICES = [
    (3, 1, 'zz', 30, 1, 2),
    (1, 1, 'xx', 10, 2, 1),
    (4, 1, '', 40, 1, 2),
    (2, 1, None, 20, 3, 1),
    (5, 3, None, 7, 1, 1),
]


def source(backend, order_by='$id'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('aggregation_contracts', implementation=backend).packages().package(
        'app', sqlschema='pg_temp' if backend == 'postgres' else 'main')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name')
    vat = pkg.table('vat', pkey='id')
    vat.column('id', dtype='L')
    vat.column('rate', dtype='N')
    invoice = pkg.table('invoice', pkey='id', order_by=order_by)
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('app.customer.id', relation_name='invoices')
    invoice.column('code')
    invoice.column('total', dtype='N')
    invoice.column('qty', dtype='L')
    invoice.column('vat_id', dtype='L').relation('app.vat.id')
    invoice.formulaColumn('double_total', '$total * 2', dtype='N', static=True)
    invoice.formulaColumn('adjusted', '$double_total + :offset', var_offset=5, dtype='N')
    invoice.formulaColumn('adjusted_again', '$double_total + :offset', var_offset=7, dtype='N')
    invoice.aliasColumn('tax_rate', '@vat_id.rate')
    customer.virtualRelation('large_invoices', relation='@invoices', condition='$total>15')
    customer.virtualRelation('above_customer', relation='@invoices',
                             condition='$total>:var_minimum', var_minimum='$id * 15')
    return config


@pytest.fixture(scope='module', params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
def backend(request):
    return request.param


@pytest.fixture(scope='module')
def connection(backend):
    connection = (psycopg.connect(postgres_dsn()) if backend == 'postgres'
                  else sqlite3.connect(':memory:'))
    try:
        cursor = connection.cursor()
        for name, columns in [
            ('customer', 'id BIGINT, name TEXT'),
            ('vat', 'id BIGINT, rate NUMERIC'),
            ('invoice', 'id BIGINT, customer_id BIGINT, code TEXT, total NUMERIC, qty BIGINT, vat_id BIGINT'),
        ]:
            # No application DML: only test fixture SQL, isolated to this connection.
            kind = 'TEMP ' if backend == 'postgres' else ''
            cursor.execute(f'CREATE {kind}TABLE app_{name} ({columns})')
        marker = '%s' if backend == 'postgres' else '?'
        for name, rows in [('customer', [(1, 'A'), (2, 'B'), (3, 'C')]),
                           ('vat', [(1, 10), (2, 20)]), ('invoice', INVOICES)]:
            cursor.executemany(f'INSERT INTO app_{name} VALUES ({",".join([marker] * len(rows[0]))})', rows)
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture(scope='module')
def model(backend):
    config = source(backend)

    def forbidden(*args, **kwargs):
        pytest.fail('Aggregation compilation attempted database I/O')

    with pytest.MonkeyPatch.context() as patch:
        for driver in (PostgresAdapter, SqliteAdapter):
            patch.setattr(driver, 'connect', forbidden)
            patch.setattr(driver, 'execute', forbidden)
        with build_database(config) as database:
            yield database
            assert database._connections == {}


@pytest.fixture
def xml_backend(backend):
    if backend != 'postgres':
        pytest.skip('SQLite has no to_xml capability; rejection is tested separately')
