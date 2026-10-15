"""Effective field types and owned metadata in lazy relation-tree nodes."""
from copy import deepcopy

import pytest

from asqueel import SqlDatabaseConfig


@pytest.mark.parametrize('attributes,dtype', [
    ({}, 'T'),
    ({'dtype': None}, 'T'),
    ({'size': ':20'}, 'A'),
    ({'dtype': 'L'}, 'L'),
    ({'dtype': 'T', 'size': ':20'}, 'T'),
])
def test_physical_and_related_nodes_publish_effective_dtype(attributes, dtype):
    source = SqlDatabaseConfig()
    pkg = source.source.db().packages().package('app')
    target = pkg.table('target', pkey='code')
    target.column('code', **attributes)
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('ref', name_long='Reference', ui_hint={'color': 'blue'},
                **attributes).relation('app.target.code')
    source_before = source.source.to_json()
    model = source.render(mode='objects_tree')
    table = model.table('app.item')
    column = table.column('ref')
    attributes_before = deepcopy(column.attributes)
    tree = table.relations
    field = tree.get_node('ref')
    relation = tree.get_node('@ref')

    assert field.attr['dtype'] == relation.attr['dtype'] == dtype
    assert tree.get_node('@ref.code').attr['dtype'] == dtype
    assert field.attr['name_long'] == relation.attr['name_long'] == 'Reference'
    assert relation.attr['joiner']['many_relation'] == 'app.item.ref'
    assert relation.resolver.parentpath[0] is column
    relation.attr['ui_hint']['color'] = 'red'
    assert field.attr['ui_hint']['color'] == 'blue'
    assert column.attributes == attributes_before
    assert source.source.to_json() == source_before


@pytest.mark.parametrize('attributes,dtype', [({}, 'T'), ({'dtype': 'L'}, 'L')])
def test_virtual_relation_publishes_its_own_effective_dtype(attributes, dtype):
    source = SqlDatabaseConfig()
    pkg = source.source.db().packages().package('app')
    pkg.table('target', pkey='id').column('id', dtype=dtype)
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('target_id', dtype=dtype)
    item.column('last_physical', dtype='X', name_long='Unrelated field')
    item.formulaColumn('computed_ref', sql_formula='$target_id', name_long='Computed reference',
                       **attributes).weak_relation('app.target.id')
    table = source.render(mode='objects_tree').table('app.item')
    node = table.relations.get_node('@computed_ref')

    assert node.attr['dtype'] == dtype
    assert node.attr['name_long'] == 'Computed reference'
    assert node.resolver.parentpath[0] is table.virtual_columns['computed_ref']
    assert node.value.get_node('id').attr['dtype'] == dtype
    assert 'computed_ref' not in table.relations


def test_composite_keys_publish_json_dtype_at_every_relation_depth():
    source = SqlDatabaseConfig()
    pkg = source.source.db().packages().package('app')
    owner = pkg.table('owner', pkey='key')
    owner.column('code')
    owner.column('year', dtype='L')
    owner.compositeColumn('key', columns='code,year')
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('code')
    item.column('year', dtype='L')
    item.compositeColumn('ref', columns='code,year', name_long='Owner key').relation('app.owner.key')
    pkg.table('detail', pkey='id').column('id', dtype='L').relation('app.item.id')
    model = source.render(mode='objects_tree')
    table = model.table('app.item')
    ref = table.composites['ref']
    before = deepcopy(ref.attributes)

    assert ref.dtype == model.table('app.owner').column('key').dtype == 'JS'
    node = table.relations.get_node('@ref')
    nested = model.table('app.detail').relations.get_node('@id.@ref')
    for relation in (node, nested):
        assert relation.attr['dtype'] == 'JS'
        assert relation.attr['columns'] == 'code,year'
        assert relation.attr['name_long'] == 'Owner key'
        assert relation.attr['joiner']['one_relation'] == 'app.owner.key'
        assert relation.resolver.parentpath[-1] is ref
        assert relation.value.get_node('code').attr['dtype'] == 'T'
    assert model.physical_columns(table, 'ref') == ('code', 'year')
    assert 'ref' not in table.relations
    assert ref.attributes == before
