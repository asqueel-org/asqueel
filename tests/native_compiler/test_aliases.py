"""Alias columns retain declaration identity while resolving values at their owner."""

import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.write_compiler import WriteCompiler

ALIASES = ('customer_code', 'country_name', 'via_alias', 'twice')


@pytest.fixture
def db():
    config = SqlDatabaseConfig()
    pkg = config.source.db('aliases', implementation='postgres').packages().package('app')
    country = pkg.table('country', pkey='id')
    country.column('id', dtype='L')
    country.column('name', sqlname='country_name')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('country_id', dtype='L').relation('app.country.id')
    customer.aliasColumn('country', '@country_id.name')
    customer.column('code', dtype='L', sqlname='numeric_code')
    customer.formulaColumn('double', '$code * 2', dtype='L')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('app.customer.id')
    invoice.aliasColumn('customer_code', '@customer_id.code')
    invoice.aliasColumn('country_name', '@customer_id.@country_id.name')
    invoice.aliasColumn('via_alias', '@customer_id.country')
    invoice.aliasColumn('twice', '@customer_id.double')
    database = AsqueelDb(config)
    try:
        yield database
    finally:
        database.closeConnection()


def test_wildcard_excludes_dynamic_aliases_and_dml_defaults_stay_physical(db):
    assert 'country_name' not in [c.name for c in db.compiler.select('app.invoice').columns]
    assert 'country_name' in [c.name for c in db.compiler.select('app.invoice', '$country_name').columns]
    writer = WriteCompiler(db.adapter)
    table = db.table('app.invoice').model
    record = {'id': 1, 'customer_id': 2, **{name: 'x' for name in ALIASES}}
    results = [writer.insert(table, record, {}),
               writer.update(table, record, {}),
               writer.delete(table, record, {})]
    for query in results:
        assert 'JOIN' not in query.sql
        for name in ALIASES:
            assert name not in query.sql
            assert name not in query.params
