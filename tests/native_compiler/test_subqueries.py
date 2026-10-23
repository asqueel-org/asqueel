"""Correlated formulas preserve scope, bind values, and visibility policies."""
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.write_compiler import WriteCompiler

VIRTUALS = ('total', 'present', 'named', 'plus', 'local')


def spec(**options):
    return {'table': 'app.item', 'where': '$owner_id=#THIS.id', 'columns': 'SUM($amount)', **options}


@pytest.fixture
def db():
    config = SqlDatabaseConfig()
    pkg = config.source.db('subqueries', implementation='postgres').packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('threshold', dtype='N')
    owner.formulaColumn('total', select=spec(), dtype='N', x_identity='stable-total')
    owner.formulaColumn('present', exists=spec(columns='1'), dtype='B')
    owner.formulaColumn('named', 'COALESCE(#low,0)+COALESCE(#high,0)', dtype='N',
                        select_low=spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                        sqlparams={'threshold': 1}),
                        select_high=spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                         sqlparams={'threshold': 5}))
    owner.formulaColumn('plus', '$total + 1')
    owner.formulaColumn('local', '$id + 1')
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('owner_id', dtype='L')
    item.column('amount', dtype='N')
    wrapper = pkg.table('wrapper')
    wrapper.column('id', dtype='L')
    wrapper.column('owner_id', dtype='L').relation('app.owner.id')
    database = AsqueelDb(config)
    try:
        yield database
    finally:
        database.closeConnection()


def writer(db):
    return WriteCompiler(db.adapter)


def test_dml_default_excludes_subqueries_and_explicit_request_rejected(db):
    query = writer(db).insert(db.table('app.owner').model, {'id': 1}, {})
    for name in ('total', 'present', 'named'):
        assert name not in query.sql


def test_default_returning_excludes_transitive_virtual_dependencies(db):
    table = db.table('app.owner').model
    record = {'id': 1, 'threshold': 2, **{name: 3 for name in VIRTUALS}}
    for query in [writer(db).insert(table, record, {}),
                  writer(db).update(table, record, {}),
                  writer(db).delete(table, record, {})]:
        for name in VIRTUALS:
            assert f'"{name}"' not in query.sql
            assert name not in query.params
