"""GenroPy a659df9d36 / 170495f80a: replace a virtual kind, keep its identity."""
from copy import deepcopy

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler


def recipe(dialect='sqlite'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('redefinition', implementation=dialect).packages().package('app', sqlschema='main')
    person = pkg.table('person', pkey='id')
    person.column('id', dtype='L')
    person.column('name', dtype='T')
    table = pkg.table('cast', pkey='id')
    table.column('id', dtype='L')
    table.column('person_id', dtype='L').relation('app.person.id')
    return config, table


def declare(target, tag, **attrs):
    definition = {'aliasColumn': {'relation_path': '@person_id.name'},
                  'formulaColumn': {'sql_formula': "'from_formula'"}}
    return getattr(target, tag)('value', **definition[tag], **attrs)


@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('layered', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('dialect', ['sqlite', 'postgres'])
def test_alias_formula_redefinition(grouped, layered, reverse, dialect):
    first, second = ('formulaColumn', 'aliasColumn') if reverse else ('aliasColumn', 'formulaColumn')
    config, table = recipe(dialect)
    target = table.colgroup('grp', name_long='Group') if grouped else table
    target.formulaColumn('before', '1', dtype='L')
    original = declare(target, first, dtype='T', name_long='Original', name_short='V',
                       comment='Keep', static=True, x_ui_color='blue')
    target.formulaColumn('after', '2', dtype='L')
    old_group = original.get_attr('group')
    before = deepcopy(dict(original.attr))
    if layered:
        overlay, overlay_table = recipe(dialect)
        destination = overlay_table.colgroup('grp', name_long='Group') if grouped else overlay_table
        incoming = declare(destination, second, name_long='Replacement')
        incoming_before = deepcopy(dict(incoming.attr))
        config = _owned_handler(overlay, [config]).builder
        assert original.attr == before
        assert incoming.attr == incoming_before
        node = config.source['db.packages.app.tables.cast.virtual_columns.value']
    else:
        node = declare(target, second, name_long='Replacement')
        assert node is original
    assert node.node_tag == second
    assert node.get_attr('name_long') == 'Replacement'
    for name in ('dtype', 'name_short', 'comment', 'static', 'x_ui_color'):
        assert node.get_attr(name) == before[name]
    assert node.get_attr('group') == old_group
    obsolete = 'sql_formula' if reverse else 'relation_path'
    assert obsolete not in node.attr
    assert [n.label for n in node.parent_bag] == ['before', 'value', 'after']
    config.validate_model()
    model = config.render(mode='objects_tree')
    assert model.table('app.cast').virtual_columns['value'].tag == second
    with SqlDatabase(model=model, config=_owned_handler(config)) as db:
        compiled = db.table('app.cast').query('$value').compiled
        assert compiled.sql.count('LEFT JOIN') == int(reverse)
        assert ("'from_formula'" in compiled.sql) is not reverse
        assert not db._connections


@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('tag', ['aliasColumn', 'formulaColumn'])
def test_relabel_preserves_virtual_definition(grouped, tag):
    base, table = recipe()
    target = table.colgroup('grp') if grouped else table
    original = declare(target, tag, name_long='Old')
    with base.contribution('label'):
        assert declare(target, tag, name_long='New') is original
    if tag == 'formulaColumn':
        assert original.get_attr('sql_formula') == "'from_formula'"
    else:
        assert original.get_attr('relation_path') == '@person_id.name'
    assert original.get_attr('name_long') == 'New'
    base.validate_model()


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('layered', [False, True])
def test_physical_virtual_change_still_rejected(reverse, layered):
    config, table = recipe()
    if reverse:
        table.formulaColumn('value', '1', dtype='L')
    else:
        table.column('value', dtype='L')
    overlay, destination = recipe() if layered else (config, table)
    if reverse:
        destination.column('value', dtype='L')
    else:
        destination.formulaColumn('value', '1', dtype='L')
    with pytest.raises(ValueError, match='conflicting element kinds'):
        _owned_handler(overlay, [config] if layered else None)


def test_same_kind_conflict_rules_are_unchanged():
    config, table = recipe()
    table.formulaColumn('value', '1')
    with pytest.raises(ValueError, match='conflicting'):
        table.formulaColumn('value', '2')
    with config.contribution('later'):
        table.formulaColumn('value', '2')
    assert table.virtual_columns().value.get_node('value').get_attr('sql_formula') == '2'


DEFINITIONS = {
    'aliasColumn': {'relation_path': '@person_id.name'},
    'formulaColumn': {'sql_formula': '#rows', 'select_rows': {'table': 'app.cast', 'columns': 'MAX($id)'}},
    'subQueryColumn': {'query': {'table': 'app.cast', 'columns': 'MAX($id)'}, 'mode': 'json'},
    'pyColumn': {'py_method': 'calculate_value', 'required_columns': '$id'},
    'bagItemColumn': {'bagcolumn': 'payload', 'itempath': 'name'},
}


@pytest.mark.parametrize('old,new', [(a, b) for a in DEFINITIONS for b in DEFINITIONS if a != b])
def test_native_definition_attributes_follow_the_new_virtual_kind(old, new):
    config, table = recipe()
    table.column('payload', dtype='X')
    extras = {'static': True} if old in ('aliasColumn', 'formulaColumn', 'pyColumn') else {}
    node = getattr(table, old)('value', **DEFINITIONS[old], **extras, dtype='T', name_long='Value',
                               x_ui_color='blue', var_threshold=7)
    assert getattr(table, new)('value', **DEFINITIONS[new]) is node
    for key in DEFINITIONS[old].keys() - DEFINITIONS[new].keys():
        if key in ('select_rows', 'required_columns', 'mode'):
            assert node.get_attr(key) == DEFINITIONS[old][key]
        else:
            assert key not in node.attr
    for key, value in DEFINITIONS[new].items():
        assert node.get_attr(key) == value
    assert node.get_attr('dtype') == 'T'
    assert node.get_attr('name_long') == 'Value'
    assert node.get_attr('x_ui_color') == 'blue'
    assert node.get_attr('var_threshold') == 7
    for key, value in extras.items():
        assert node.get_attr(key) == value
    config.validate_model()
    assert config.render(mode='objects_tree').table('app.cast').virtual_columns['value'].tag == new


def test_inherited_attributes_survive_composition_of_an_already_redefined_source():
    base, table = recipe()
    table.aliasColumn('value', '@person_id.name')
    overlay, table = recipe()
    table.formulaColumn('value', **DEFINITIONS['formulaColumn'], static=True,
                        parameters={'threshold': 7})
    table.aliasColumn('value', '@person_id.name')
    config = _owned_handler(overlay, [base]).builder
    config.validate_model()
    column = config.render(mode='objects_tree').table('app.cast').virtual_columns['value']
    assert column.attributes['static'] is True
    assert column.attributes['select_rows'] == DEFINITIONS['formulaColumn']['select_rows']
    assert column.attributes['parameters'] == {'threshold': 7}
    assert 'sql_formula' not in column.attributes


def test_redefinition_does_not_legitimize_unknown_attributes():
    config, table = recipe()
    table.aliasColumn('value', '@person_id.name', typo='not a declared attribute')
    table.formulaColumn('value', '1')
    with pytest.raises(ValueError, match="unknown attribute 'typo'"):
        config.validate_model()
