"""Alias columns retain declaration identity while resolving values at their owner."""

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, Relation, ResolvedModel, Table


@pytest.fixture
def model():
    country = Table('country', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'),
        'name': Column('name', sql_name='country_name', ui={'label': 'Country', 'width': 20}),
    })
    customer = Table('customer', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'country_id': Column('country_id', 'L'),
        'country': Column('country', relation_path='@country.name'),
        'code': Column('code', 'L', sql_name='numeric_code'),
        'double': Column('double', 'L', formula='$code * 2'),
    }, relations={'country': Relation('country', country.key, ('country_id',), ('id',))})
    invoice = Table('invoice', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'customer_id': Column('customer_id', 'L'),
        'local_id': Column('local_id', relation_path='id'),
        'customer_code': Column('customer_code', relation_path='@customer.code', identity='stable-code'),
        'country_name': Column('country_name', relation_path='@customer.@country.name',
                               ui={'label': 'Invoice country'}, identity='stable-country'),
        'via_alias': Column('via_alias', relation_path='@customer.country'),
        'twice': Column('twice', relation_path='@customer.double'),
    }, relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return ResolvedModel({table.key: table for table in (country, customer, invoice)})


def test_wildcard_excludes_dynamic_aliases_and_dml_defaults_stay_physical(model):
    compiler = PostgresCompiler(model)
    assert 'country_name' not in [c.name for c in compiler.select('invoice').columns]
    assert 'country_name' in [c.name for c in compiler.select('invoice', '$country_name').columns]
    results = [compiler.insert('invoice', {'id': 1}),
               compiler.update('invoice', {'customer_id': 2}, '$id=:id', {'id': 1}),
               compiler.delete('invoice', '$id=:id', {'id': 1})]
    for query in results:
        assert [column.name for column in query.columns] == ['id', 'customer_id']
        assert 'JOIN' not in query.sql
    assert compiler.insert('invoice', {'id': 1}, returning='$local_id').columns[0].name == 'local_id'
