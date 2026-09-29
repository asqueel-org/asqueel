"""Alias paths across live PostgreSQL application reads and physical writes."""
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from genro_sql import SqlDatabaseConfig, SqlTable, build_database, resolve_model, to_physical_builder
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture
def alias_database():
    schema = 'aliases_' + uuid4().hex
    dsn = postgres_dsn()
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            for ddl in [
                'CREATE TABLE {}.country (id integer PRIMARY KEY, name text)',
                'CREATE TABLE {0}.customer (id integer PRIMARY KEY, name text, country_id integer REFERENCES {0}.country(id))',
                'CREATE TABLE {0}.invoice (id integer PRIMARY KEY, customer_id integer REFERENCES {0}.customer(id), amount integer)',
                "INSERT INTO {}.country VALUES (1,'Italy')",
                "INSERT INTO {}.customer VALUES (1,'Alice',1),(2,'Bob',NULL)",
                'INSERT INTO {}.invoice VALUES (1,1,10),(2,2,20),(3,NULL,30)',
            ]:
                observer.execute(sql.SQL(ddl).format(sql.Identifier(schema)))

            class Invoice(SqlTable):
                def trigger_onUpdating(self, record, old_record=None):
                    assert set(record) == set(old_record) == {'id', 'customer_id', 'amount'}

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    tables = root.db('aliases', conninfo=dsn).schemas().schema(
                        'app', x_sql_schema=schema).tables()
                    country = tables.table('country', pkey='id').columns()
                    country.column('id', dtype='I')
                    country.column('name', dtype='T', name_long='Country',
                                   x_ui={'label': 'Country label', 'width': 24})
                    customer = tables.table('customer', pkey='id')
                    columns = customer.columns()
                    columns.column('id', dtype='I')
                    columns.column('name', dtype='T', name_long='Customer',
                                   x_ui={'label': 'Customer label', 'width': 32})
                    columns.column('country_id', dtype='I').relation('app.country.id', foreign_key=True, x_name='country')
                    virtual = customer.virtual_columns()
                    virtual.formulaColumn('loud_name', sql_formula='upper($name)', dtype='T')
                    virtual.aliasColumn('country_name', relation_path='@country.name')
                    invoice = tables.table('invoice', pkey='id', x_table_class=Invoice)
                    columns = invoice.columns()
                    columns.column('id', dtype='I')
                    columns.column('customer_id', dtype='I').relation('app.customer.id', foreign_key=True, x_name='customer')
                    columns.column('amount', dtype='I')
                    virtual = invoice.virtual_columns()
                    virtual.aliasColumn('customer_name', relation_path='@customer.name',
                                        name_long='Buyer name', x_ui={'label': 'Buyer'})
                    virtual.aliasColumn('country_name', relation_path='@customer.@country.name')
                    virtual.aliasColumn('country_chain', relation_path='@customer.country_name')
                    virtual.aliasColumn('loud_customer', relation_path='@customer.loud_name')

            with build_database(Recipe) as db:
                yield db
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_alias_projection_filter_order_null_chains_and_formula(alias_database):
    table = alias_database.table('invoice')
    query = table.query('$id,$customer_name,$country_name,$country_chain,$loud_customer', order_by='$id')
    result = query.execute()
    assert result.rows == [
        {'id': 1, 'customer_name': 'Alice', 'country_name': 'Italy',
         'country_chain': 'Italy', 'loud_customer': 'ALICE'},
        {'id': 2, 'customer_name': 'Bob', 'country_name': None,
         'country_chain': None, 'loud_customer': 'BOB'},
        {'id': 3, 'customer_name': None, 'country_name': None,
         'country_chain': None, 'loud_customer': None},
    ]
    metadata = {column.name: column for column in result.columns}
    assert metadata['customer_name'].source == 'app.invoice.customer_name'
    assert metadata['customer_name'].dtype == 'T'
    assert metadata['customer_name'].ui['label'] == 'Buyer'
    filtered = table.query('$id,$customer_name', where='$customer_name=:name', name='Alice').fetch()
    assert filtered == [{'id': 1, 'customer_name': 'Alice'}]
    assert [r['id'] for r in table.query('$id', where='$customer_name IS NOT NULL',
                                        order_by='$customer_name DESC').fetch()] == [2, 1]


def test_alias_metadata_and_physical_projection(alias_database):
    db = alias_database
    handle = db.table('invoice').column('customer_name')
    assert handle.config('dtype') == 'T'
    assert handle.config('name_long') == 'Buyer name'
    assert handle.originalColumn is db.table('customer').column('name')
    assert handle.relation_path == '@customer.name'
    column = db.model.table('invoice').columns['country_name']
    assert column.dtype == 'T'
    assert column.ui['label'] == 'Country label'
    assert column.is_virtual
    assert column.alias_target == ('app.country', 'name')
    physical = resolve_model(to_physical_builder(db.model))
    invoice = next(table for table in physical.tables.values() if table.name == 'invoice')
    assert set(invoice.columns) == {'id', 'customer_id', 'amount'}


def test_aliases_are_read_only_and_default_dml_returning_is_physical(alias_database):
    db = alias_database
    table = db.table('invoice')
    with pytest.raises(ValueError):
        table.update({'customer_name': 'bad'}, where='$id=1')
    db.rollback()
    with pytest.raises(ValueError):
        table.insert({'id': 4, 'customer_name': 'bad'})
    db.rollback()
    with db.transaction():
        inserted = table.insert({'id': 4, 'customer_id': 1, 'amount': 40})
        assert inserted.rows == [{'id': 4, 'customer_id': 1, 'amount': 40}]
        updated = table.update({'amount': 41}, where='$id=4')
        assert updated.rows == [{'id': 4, 'customer_id': 1, 'amount': 41}]
        assert table.record(4).output()['customer_name'] == 'Alice'
        deleted = table.delete(4)
        assert deleted.rows == [{'id': 4, 'customer_id': 1, 'amount': 41}]
