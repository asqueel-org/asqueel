"""A system code is an optional column, independent of system records."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from asqueel.projection import to_physical_builder


def source(**fields):
    config = SqlDatabaseConfig()
    table = config.source.db('test').packages().package('adm', sqlschema='adm').table('htag')
    table.options().sys_fields(**fields)
    return config, table


def test_syscode_is_opt_in_and_does_not_expand_the_source():
    for fields in ({}, {'syscode': False}, {'syscode': True, 'enabled': False}):
        config, _ = source(**fields)
        assert '__syscode' not in resolve_model(config).table('adm.htag').columns
    config, table = source(syscode=True)
    assert table.value.get_node('columns') is None
    first = resolve_model(config)
    assert first is not resolve_model(config)
    assert SqlMigrationRenderer(to_physical_builder(first)).render() == SqlMigrationRenderer(to_physical_builder(resolve_model(config))).render()
    assert table.value.get_node('columns') is None
    resolved = first.table('adm.htag')
    code = resolved.columns['__syscode']
    assert code.dtype == 'A'
    assert {key: code.attributes[key] for key in ('size', 'indexed', 'unique')} == {
        'size': ':20', 'indexed': True, 'unique': True}
    assert resolved.pkey == 'id'
    assert resolved.get('options') is None or 'system_records' not in resolved['options']
    assert not {'__protected_by_syscode', '__invalid_by_duplicate_sysrecord'} & resolved.columns.keys()
    assert not {'default', 'sqldefault', 'x_generation', 'onInserting'} & code.attributes.keys()
    physical = SqlMigrationRenderer(to_physical_builder(first)).render()
    attrs = physical['root']['schemas']['adm']['tables']['adm_htag']['columns']['__syscode']['attributes']
    assert attrs['unique'] is True
    assert attrs['size'] == '0:20'  # Logical :20 is normalized only at the storage boundary.
    assert 'notnull' not in attrs


def test_syscode_can_be_disabled_by_a_later_contribution_without_removing_explicit_columns():
    config, table = source(syscode=True)
    with config.contribution('disable'):
        table.options().sys_fields(syscode=False)
    assert '__syscode' not in resolve_model(config).table('adm.htag').columns
    table.column('__syscode', size=':20', unique=True, indexed=True)
    assert '__syscode' in resolve_model(config).table('adm.htag').columns


def test_syscode_preserves_an_explicit_primary_key_and_column_labels():
    config, table = source(id=False, syscode=True)
    config.source['db.packages.adm'].table('htag', pkey='__syscode')
    table.column('__syscode', size=':20', unique=True, indexed=True, name_long='Internal code')
    resolved = resolve_model(config).table('adm.htag')
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
        resolve_model(config)


@pytest.mark.parametrize('value', [None, 1, 'yes', {}])
def test_syscode_accepts_only_a_boolean(value):
    with pytest.raises(ValueError):
        source(syscode=value)
