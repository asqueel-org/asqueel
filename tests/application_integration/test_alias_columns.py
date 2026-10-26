"""Alias paths across live PostgreSQL application reads and physical writes."""
from tests.unit_of_work import completed
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from tests.native_support import postgres_dsn
from tests.package_layout_support import write_layout

pytestmark = pytest.mark.postgresql

INVOICE = '''
class Table:
    def config_db(self, pkg):
        invoice = pkg.table('invoice', pkey='id')
        columns = invoice.columns()
        columns.column('id', dtype='I')
        columns.column('customer_id', dtype='I').relation('app.customer.id', foreign_key=True)
        columns.column('amount', dtype='I')
        virtual = invoice.virtual_columns()
        virtual.aliasColumn('customer_name', relation_path='@customer_id.name',
                            name_long='Buyer name', static=True)
        virtual.aliasColumn('country_name', relation_path='@customer_id.@country_id.name')
        virtual.aliasColumn('country_chain', relation_path='@customer_id.country_name')
        virtual.aliasColumn('loud_customer', relation_path='@customer_id.loud_name')

    def trigger_onUpdating(self, record, old_record=None):
        assert set(record) == set(old_record) == {'id', 'customer_id', 'amount'}
'''


@pytest.fixture
def alias_database(tmp_path):
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

            path = write_layout(tmp_path / 'app', invoice=INVOICE)

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    tables = root.db('aliases', implementation='postgres', conninfo=dsn).packages().package(
                        'app', sqlschema=schema, sqlprefix=False, path=path).tables()
                    country = tables.table('country', pkey='id').columns()
                    country.column('id', dtype='I')
                    country.column('name', dtype='T', name_long='Country')
                    customer = tables.table('customer', pkey='id')
                    columns = customer.columns()
                    columns.column('id', dtype='I')
                    columns.column('name', dtype='T', name_long='Customer')
                    columns.column('country_id', dtype='I').relation('app.country.id', foreign_key=True)
                    virtual = customer.virtual_columns()
                    virtual.formulaColumn('loud_name', sql_formula='upper($name)', dtype='T')
                    virtual.aliasColumn('country_name', relation_path='@country_id.name')

            db = AsqueelDb(Recipe).session()
            try:
                yield db
            finally:
                db.closeConnection()
                db.shared.close()
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_aliases_are_not_written_and_default_dml_returning_is_physical(alias_database):
    db = alias_database
    table = db.table('app.invoice')
    table.insert({'id': 4, 'customer_name': 'bad'})
    assert [dict(row) for row in table.query(columns='$customer_id,$customer_name', where='$id=4').fetch()] == [
        {'customer_id': None, 'customer_name': None}]
    db.rollback()
    with completed(db):
        inserted = table.insert({'id': 4, 'customer_id': 1, 'amount': 40})
        assert inserted == {'id': 4, 'customer_id': 1, 'amount': 40}
        updated = table.update({'id': 4, 'customer_id': 1, 'amount': 41},
                               old_record={'id': 4, 'customer_id': 1, 'amount': 40})
        assert updated == {'id': 4, 'customer_id': 1, 'amount': 41}
        assert table.query(columns='$customer_name', where='$id=4').fetch()[0]['customer_name'] == 'Alice'
        table.delete({'id': 4, 'customer_id': 1, 'amount': 41})
        assert table.query(where='$id=4').fetch() == []
