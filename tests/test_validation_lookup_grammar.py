"""Legacy lookup validations are model data, never database operations."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from asqueel.configuration import _copy_recipe


def source():
    builder = SqlDatabaseConfig()
    table = builder.source.db('example', implementation='postgres').packages().package('app').table('item')
    return builder, table


@pytest.mark.parametrize('rule', ['exist', 'nodup'])
@pytest.mark.parametrize('value', [True, False, '', 'external.table.code', None, 1, [], {}])
def test_lookup_rules_keep_values_without_resolving_targets_or_executing(rule, value):
    builder, table = source()
    expected = {rule: value, f'{rule}_error': 'Check failed'}
    table.column('embedded', **{f'validate_{key}': item for key, item in expected.items()})
    model = resolve_model(builder)
    assert model.table('app.item').columns['embedded'].validations == expected
    restored = resolve_model(_copy_recipe(builder))
    assert restored.table('app.item').columns['embedded'].validations == expected
    physical = SqlMigrationRenderer(builder).render()['root']['schemas']['public']['tables']['app_item']
    assert not physical.get('relations')
    assert not physical['columns']['embedded']['attributes'].get('unique')


def test_legacy_lookup_parameters_survive_composition_and_round_trip():
    builder, table = source()
    expected = {
        'nodup': 'external.table.code', 'nodup_relative': 'parent_id',
        'nodup_condition': '$parent_id=:parent AND $active=:active',
        'nodup_parent': 'parent-1', 'nodup_active': True,
        'nodup_sqlparams': {'scope': 'local'},
        'nodup_warning': 'Already present', 'nodup_iswarning': True,
        'nodup_if': 'value != null', 'nodup_duplicated_value': 'Duplicate',
        'exist': True, 'exist_if': 'value != null', 'exist_warning': 'Not found',
    }
    table.column('code', **{f'validate_{key}': value for key, value in expected.items()})
    with builder.contribution('application'):
        table.column('code', validate_nodup_relative='account_id', validate_exist=False)
    expected.update(nodup_relative='account_id', exist=False)
    builder.validate_source()
    model = resolve_model(_copy_recipe(builder))
    assert model.table('app.item').columns['code'].validations == expected


@pytest.mark.parametrize('key,value', [
    ('empty', 'default'), ('call', 'checkCode(value)'), ('remote', 'check_code'),
    ('len', 'uninterpreted'), ('min', 10), ('max', 1),
    ('notnull_warning', 'Required'), ('exists', True), ('noup', True),
    ('name', 'any.value'), ('metadata', 'uninterpreted'),
])
def test_validation_data_survives_all_source_forms_without_vocabulary_checks(key, value):
    builder, table = source()
    table.column('embedded', **{f'validate_{key}': value})
    node = table.column('imported')
    node.attr[f'validate_{key}'] = value
    builder.validate_source()
    model = resolve_model(_copy_recipe(builder))
    for name in ('embedded', 'imported'):
        assert model.table('app.item').columns[name].validations == {key: value}
