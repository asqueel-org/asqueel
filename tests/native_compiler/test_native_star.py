"""Legacy starColumns ordering and bagFields, shared by root and child SELECTs."""
import pytest

from asqueel import SqlDatabaseConfig, build_database


@pytest.fixture(params=['postgresql', 'sqlite'])
def table(request):
    config = SqlDatabaseConfig()
    pkg = config.source.db('stars', implementation=request.param).packages().package('sales')
    tbl = pkg.table('item', pkey='id')
    tbl.column('id', dtype='L')
    tbl.formulaColumn('static_value', '$id + :amount', var_amount=2, static=True, dtype='L')
    tbl.column('payload', dtype='X')
    tbl.column('description')
    tbl.formulaColumn('dynamic_value', '$id + 3', dtype='L')
    tbl.formulaColumn('static_xml', "'<r/>'", dtype='X', static=True)
    tbl.formulaColumn('not_implemented', '#PREF(x,1)')
    return build_database(config).table('sales.item')


def names(query):
    return [col.name for col in query.compiled.columns]


def test_star_selects_physical_then_static_virtual_columns(table):
    assert names(table.query()) == ['id', 'description', 'static_value', 'static_xml']
    assert names(table.query(bagFields=True)) == ['id', 'payload', 'description', 'static_value', 'static_xml']
    assert names(table.query('$payload,$dynamic_value')) == ['payload', 'dynamic_value']
    assert list(table.query().compiled.params.values()) == [2]


def test_returning_keeps_all_physical_columns(table):
    writer = table.db.write_compiler
    assert 'RETURNING' not in writer.delete(table.model, {'id': 1}, {}).sql
    virtuals = ('static_value', 'dynamic_value', 'static_xml', 'not_implemented')
    inserted = writer.insert(table.model, {'id': 1, **{name: 1 for name in virtuals}}, {})
    for name in virtuals:
        assert f'"{name}"' not in inserted.sql


def test_bag_fields_requires_boolean(table):
    with pytest.raises(ValueError, match='bagFields must be a boolean'):
        table.query(bagFields='true').compiled


def test_static_alias_uses_existing_relation_join():
    config = SqlDatabaseConfig()
    pkg = config.source.db('aliases').packages().package('sales')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('label')
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('owner_id', dtype='L').relation('sales.owner.id')
    item.aliasColumn('owner_label', '@owner_id.label', static=True)
    item.aliasColumn('dynamic_label', '@owner_id.label')
    query = build_database(config).table('sales.item').query().compiled
    assert [col.name for col in query.columns] == ['id', 'owner_id', 'owner_label']
    assert query.sql.count('LEFT JOIN') == 1


@pytest.mark.parametrize('backend', ['postgresql', 'sqlite'])
def test_subquery_star_uses_same_bag_fields_option(backend):
    config = SqlDatabaseConfig()
    pkg = config.source.db('child', implementation=backend).packages().package('sales')
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    payload = pkg.table('payload')
    payload.column('data', dtype='X')
    item.formulaColumn('data', select=dict(table='sales.payload', columns='*', where='TRUE',
                                         limit=1, bagFields=True), dtype='X')
    sql = build_database(config).table('sales.item').query('$data').compiled.sql
    assert '"data" AS "data"' in sql
