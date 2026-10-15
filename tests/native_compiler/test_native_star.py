"""Legacy starColumns ordering and bagFields, shared by root and child SELECTs."""
import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.contracts import UnsupportedFeatureError


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
    query = table.db.compiler.delete(table.fullname, '$id=:id', dict(id=1))
    assert [col.name for col in query.columns] == ['id', 'payload', 'description']


def test_bag_fields_requires_boolean(table):
    with pytest.raises(ValueError, match='bagFields must be a boolean'):
        table.query(bagFields='true').compiled


def test_static_unimplemented_column_is_not_silently_dropped(table):
    from dataclasses import replace
    model = table.db.model
    item = table.model
    column = item.columns['not_implemented']
    changed = replace(column, attributes={**column.attributes, 'static': True})
    changed_table = replace(item, columns={**item.columns, column.name: changed})
    compiler = table.db.compiler
    compiler.model = replace(model, tables={**model.tables, item.key: changed_table})
    with pytest.raises(UnsupportedFeatureError, match='PREF'):
        compiler.select(item.key)


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


def test_record_keeps_physical_x_fields_unless_explicitly_excluded(table):
    assert 'payload' in names(table.record(1).query)
    assert 'payload' not in names(table.record(1, bagFields=False).query)
    assert 'dynamic_value' not in names(table.record(1).query)
