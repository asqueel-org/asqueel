"""A system code is an optional column, independent of system records."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig


def source(**fields):
    config = SqlDatabaseConfig()
    table = config.source.db('test').packages().package('adm', sqlschema='adm').table('htag')
    table.options().sys_fields(**fields)
    return config, table


def test_syscode_is_opt_in_and_does_not_expand_the_source():
    for fields in ({}, {'syscode': False}, {'syscode': True, 'enabled': False}):
        config, _ = source(**fields)
        assert '__syscode' not in AsqueelDb(config).model.table('adm.htag').columns
    config, table = source(syscode=True)
    assert table.value.get_node('columns') is None
    first = AsqueelDb(config).model
    assert first is not AsqueelDb(config).model
    assert first.db.config.builder.render(mode='migration') == (AsqueelDb(config).config.builder).render(mode='migration')
    assert table.value.get_node('columns') is None
    resolved = first.table('adm.htag')
    code = resolved.columns['__syscode']
    assert code.dtype == 'A'
    assert {key: code.attributes[key] for key in ('size', 'indexed', 'unique')} == {
        'size': ':20', 'indexed': True, 'unique': True}
    assert resolved.pkey == 'id'
    assert resolved.get('options') is None or 'system_records' not in resolved['options']
    assert not {'__protected_by_syscode', '__invalid_by_duplicate_sysrecord'} & resolved.columns.keys()
    assert not {'default', 'sql_default', 'x_generation', 'onInserting'} & code.attributes.keys()
    physical = first.db.config.builder.render(mode='migration')
    attrs = physical['root']['schemas']['adm']['tables']['adm_htag']['columns']['__syscode']['attributes']
    assert attrs['unique'] is True
    assert attrs['size'] == '0:20'  # Logical :20 is normalized only at the storage boundary.
    assert 'notnull' not in attrs


def test_syscode_can_be_disabled_by_a_later_contribution_without_removing_explicit_columns():
    config, table = source(syscode=True)
    with config.contribution('disable'):
        table.options().sys_fields(syscode=False)
    assert '__syscode' not in AsqueelDb(config).model.table('adm.htag').columns
    table.column('__syscode', size=':20', unique=True, indexed=True)
    assert '__syscode' in AsqueelDb(config).model.table('adm.htag').columns


def test_syscode_preserves_an_explicit_primary_key_and_column_labels():
    config, table = source(id=False, syscode=True)
    config.source['db.packages.adm'].table('htag', pkey='__syscode')
    table.column('__syscode', size=':20', unique=True, indexed=True, name_long='Internal code')
    resolved = AsqueelDb(config).model.table('adm.htag')
    assert resolved.pkey == '__syscode'
    assert 'id' not in resolved.columns
    assert resolved.columns['__syscode'].attributes['name_long'] == 'Internal code'


@pytest.mark.parametrize('attributes', [
    {'dtype': 'L'}, {'size': ':30'}, {'unique': False}, {'indexed': False},
])
def test_syscode_does_not_silently_override_an_incompatible_explicit_column(attributes):
    config, table = source(syscode=True)
    table.column('__syscode', **attributes)
    with pytest.raises(ValueError, match='conflicts with sys_fields'):
        AsqueelDb(config).model


@pytest.mark.parametrize('value', [None, 1, 'yes', {}])
def test_syscode_accepts_only_a_boolean(value):
    with pytest.raises(ValueError):
        source(syscode=value)
