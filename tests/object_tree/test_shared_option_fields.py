"""Composition contracts against the independent legacy model, ignoring order."""

import pytest

from asqueel import AsqueelDb
from asqueel.object_tree import DbVirtualColumnObj
from examples.test_invoice_pg import source
from tests.object_tree.test_invoice import LEGACY, RELATIONS


# Fields read or contributed to by multiple options, or by an option and an
# explicit declaration, in the 74 native recipes. These are real model cases.
SHARED = {
    'adm.htag': ('code', 'description', 'id'),
    'adm.htmltemplate': ('id',),
    'adm.htmltemplate_atc': ('id',),
    'adm.menu': ('id', 'label'),
    'adm.user': ('id',),
    'invc.product_group': ('_row_count', 'code', 'id'),
    'invc.product_type': ('description', 'id'),
    'sys.widget': ('id', 'name'),
}

# Legacy attributes written by options that asqueel has no reader for: the live
# column does not carry them.
NO_READER = {'_sysfield', '_sendback', 'counter', '_counter_fkey', 'templates', 'subfields', 'broadcast',
             'relidx', '_relidx_fkey', 'format', 'fkeyToMaster', 'audit'}


@pytest.fixture(scope='module')
def model():
    config = source()
    before = config.source.to_json()
    result = AsqueelDb(config).model
    assert config.source.to_json() == before
    return result


def legacy_table(key):
    pkg, table = key.split('.')
    return LEGACY[pkg]['children']['tables']['children'][table]


def assert_legacy_attributes(column, expected):
    for key, value in expected.items():
        if key in ('tag', '_owner_package'):
            # tag is the object class; _owner_package is legacy build provenance.
            continue
        if key in NO_READER and key not in column.attributes:
            continue
        if key == 'dtype':
            actual = column.dtype
        elif key == 'virtual_column':
            actual = isinstance(column, DbVirtualColumnObj)
        elif key == 'size':
            actual, value = column.attributes.get(key), str(value)
        elif key == 'readOnly':
            actual = column.attributes.get('readOnly')
            value = value in (True, 'y', 'true')
        elif key.startswith('validate_'):
            actual = column.validations.get(key.removeprefix('validate_'))
        else:
            actual = column.attributes.get(key)
        assert actual == value, (column.fullname, key, actual, value)


@pytest.mark.parametrize('table,name', [(table, name) for table, fields in SHARED.items() for name in fields])
def test_shared_fields_preserve_legacy_attributes_and_identity(model, table, name):
    owner = model.table(table)
    column = owner.column(name)
    expected = legacy_table(table)['children']['columns']['children'][name]['attributes']
    assert_legacy_attributes(column, expected)
    assert owner.columns[name] is column
    assert model.column(f'{table}.{name}') is column
    assert column.parent is owner.columns
    declarations = owner.structnode.value.get_item('columns')
    assert sum(node.label == name for node in declarations) == 1
    assert name not in owner.virtual_columns


def test_hierarchical_counter_keeps_numeric_base_and_text_derivatives(model):
    table = model.table('invc.product_group')
    counter = table.column('_row_count')
    assert counter.dtype == 'L'
    assert counter.attributes['name_long'] == '!![en]Counter'
    assert counter.attributes['group'] == 'zzz'
    # The hierarchical branch does not install the ordinary setRowCounter hook.
    assert 'onInserting' not in counter.attributes
    for name in ('hierarchical__row_count', '_parent_h__row_count', '_h_count', '_parent_h_count'):
        column = table.column(name)
        assert column.dtype == 'T'
        assert_legacy_attributes(column, legacy_table(table.fullname)['children']['columns']['children'][name]['attributes'])
    assert table.column('hierarchical__row_count').attributes['hierarchical_field_of'] == '_row_count'
    assert table.dbtable.hierarchicalHandler.fields == ['code', '_row_count', 'pkey']
    assert table.attributes['order_by'] == '$_h_sortcol'
    formula = legacy_table(table.fullname)['children']['virtual_columns']['children']['_h_sortcol']['attributes']
    assert_legacy_attributes(table.column('_h_sortcol'), formula)


@pytest.mark.parametrize('key,field,target', [
    ('invc.product_group', 'parent_id', 'invc.product_group.id'),
    ('adm.htmltemplate_atc', 'maintable_id', 'adm.htmltemplate.id'),
])
def test_relations_survive_composition_without_duplicates(model, key, field, target):
    table = model.table(key)
    relation = table.relations.get_node('@' + field)
    expected = RELATIONS['relations'][key + '.@' + field]
    assert relation.attr['joiner'] == expected
    assert table.column('@' + field + '.id') is model.column(target)
    declarations = table.column(field).structnode.value
    assert sum(node.node_tag == 'relation' for node in declarations) == 1
    assert table.relations.keys().count('@' + field) == 1
    assert dict(model.relations.get_node(key + '.@' + field).attr) == expected
