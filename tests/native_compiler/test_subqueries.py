"""Correlated formulas preserve scope, bind values, and visibility policies."""
from dataclasses import replace

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, Relation, ResolvedModel
from asqueel.contracts import Table, UnsupportedFeatureError


def spec(**options):
    return {'table': 'app.item', 'where': '$owner_id=#THIS.id', 'columns': 'SUM($amount)', **options}


@pytest.fixture
def model():
    owner = Table('owner', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'threshold': Column('threshold', 'N'),
        'total': Column('total', 'N', select=spec(), identity='stable-total', ui={'label': 'Total'}),
        'present': Column('present', 'B', exists=spec(columns='1')),
        'named': Column('named', 'N', formula='COALESCE(#low,0)+COALESCE(#high,0)',
                        subqueries={'low': spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                                sqlparams={'threshold': 1}),
                                    'high': spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                                 sqlparams={'threshold': 5})}),
    })
    item = Table('item', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'owner_id': Column('owner_id', 'L'), 'amount': Column('amount', 'N')})
    wrapper = Table('wrapper', schema='app', columns={'id': Column('id', 'L'),
                    'owner_id': Column('owner_id', 'L')},
                    relations={'owner': Relation('owner', owner.key, ('owner_id',), ('id',))})
    return ResolvedModel({table.key: table for table in (owner, item, wrapper)})


def change_column(model, name, column, table='owner'):
    owner = model.table(table)
    owner = replace(owner, columns={**owner.columns, name: column})
    return replace(model, tables={**model.tables, owner.key: owner})


def test_dml_default_excludes_subqueries_and_explicit_request_rejected(model):
    compiler = PostgresCompiler(model)
    query = compiler.insert('owner', {'id': 1})
    assert [column.name for column in query.columns] == ['id', 'threshold']
    for column in ('$total', '$present', '$named'):
        with pytest.raises(UnsupportedFeatureError, match='Subquery columns'):
            compiler.insert('owner', {'id': 1}, returning=column)


def test_default_returning_excludes_transitive_virtual_dependencies(model):
    model = change_column(model, 'plus', Column('plus', formula='$total + 1'))
    model = change_column(model, 'local', Column('local', formula='$id + 1'))
    compiler = PostgresCompiler(model)
    results = [compiler.insert('owner', {'id': 1}),
               compiler.update('owner', {'id': 1}, 'TRUE'), compiler.delete('owner', 'TRUE')]
    for result in results:
        assert [column.name for column in result.columns] == ['id', 'threshold']
    assert '("t0"."id" + 1) AS "local"' in compiler.insert('owner', {'id': 1}, returning='$local').sql
    with pytest.raises(UnsupportedFeatureError, match='Subquery columns'):
        compiler.insert('owner', {'id': 1}, returning='$plus')
