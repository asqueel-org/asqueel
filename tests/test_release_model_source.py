"""Contracts for the new model source, before complete object resolution."""
import pytest

from asqueel import SqlBuilder, SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from asqueel.validators import SqlModelValidationError


def source():
    builder = SqlDatabaseConfig()
    db = builder.source.db('test_invoice_pg', implementation='postgresql')
    pkg = db.packages().package('invc', sqlschema='invc', sqlprefix=True)
    return builder, db, pkg


def test_package_is_distinct_from_schema_and_containers_are_idempotent():
    builder, db, pkg = source()
    assert db.packages() is db.packages()
    assert pkg.options() is pkg.options()
    assert builder.source.get_node('db.schemas') is None
    assert builder.source['db.packages.invc'] is pkg


def test_direct_table_declarations_keep_internal_namespaces_and_standard_labels():
    builder, _, pkg = source()
    table = pkg.table('customer', pkey='id', name_long='Cliente',
                      name_short='Cli.', name_plural='Clienti', caption_field='account_name')
    table.column('id', dtype='L')
    table.column('account_name', dtype='T')
    table.formulaColumn('upper_name', sql_formula='upper($account_name)')
    table.index('name_idx', columns='account_name')
    builder.validate_model()
    path = 'db.packages.invc.tables.customer'
    assert builder.source[path + '.columns.account_name'].get_attr('dtype') == 'T'
    assert builder.source[path + '.virtual_columns.upper_name'] is not None
    assert builder.source[path + '.indexes.name_idx'] is not None
    assert table.get_attr('name_short') == 'Cli.'


def test_package_tables_are_not_ignored_by_referential_validation():
    builder, _, pkg = source()
    pkg.table('customer', pkey='missing')
    with pytest.raises(SqlModelValidationError, match='missing'):
        builder.validate_model()


def test_repeated_declaration_completes_without_reapplying_defaults():
    builder, db, pkg = source()
    table = pkg.table('customer', name_long='Cliente')
    assert pkg.table('customer', name_short='Cli.') is table
    assert pkg.table('customer') is table
    assert db.packages().package('invc') is pkg
    assert pkg.get_attr('sqlschema') == 'invc'
    assert table.get_attr('name_long') == 'Cliente'
    with pytest.raises(ValueError, match='conflicting'):
        pkg.table('customer', name_long='Altro')
    with builder.contribution('application'):
        pkg.table('customer', name_long='Cliente applicativo')
    assert table.get_attr('name_long') == 'Cliente applicativo'


def test_options_have_closed_signatures_and_are_scoped_to_the_owner():
    _, db, pkg = source()
    opts = pkg.options()
    opts.requires('sys')
    opts.type('money', dtype='N', size='14,2')
    with pytest.raises(ValueError, match='does not accept'):
        opts.type('bad', dtypo='N')
    with pytest.raises(ValueError, match='not available'):
        db.options().sys_fields()
    with pytest.raises(ValueError, match='not available'):
        pkg.options().driver(connect_timeout=10)


def test_positional_option_arguments_are_not_silently_lost():
    _, db, pkg = source()
    assert pkg.options().metadata('app', {'area': 'billing'}).get_attr('values') == {'area': 'billing'}
    assert pkg.options().requires('sys', 'adm').get_attr('packages') == ['sys', 'adm']
    with pytest.raises(TypeError, match='positional'):
        pkg.table('bad', 'unexpected')


@pytest.mark.parametrize('config', [
    {'id': {'type': 'custom'}}, {'id': {'size': '36'}},
    {'upd': {'indexed': 'yes'}}, {'upd': {'name_long': 17}},
    {'timestamp_type': 'T'}, {'id': 1},
    {'id': None},
])
def test_system_field_payloads_are_typed_and_closed(config):
    _, _, pkg = source()
    with pytest.raises(ValueError):
        pkg.table('customer').options().sys_fields(**config)


def test_options_copy_input_without_expanding_or_generating_values():
    builder, _, pkg = source()
    config = {'type': 'uuid', 'name_long': 'Identificativo'}
    option = pkg.table('customer').options().sys_fields(id=config, draft=True)
    config['type'] = 'changed'
    assert option.get_attr('id')['type'] == 'uuid'
    assert builder.source['db.packages.invc.tables.customer.columns'] is None


def test_field_dicts_merge_per_key_and_conflicts_leave_the_source_unchanged():
    builder, _, pkg = source()
    opts = pkg.table('customer').options()
    fields = opts.sys_fields(id={'type': 'uuid'})
    opts.sys_fields(id={'name_long': 'Identificativo'})
    assert fields.get_attr('id') == {'type': 'uuid', 'name_long': 'Identificativo'}
    with pytest.raises(ValueError, match='conflicting'):
        opts.sys_fields(id={'indexed': True, 'name_long': 'Conflitto'})
    assert 'indexed' not in fields.get_attr('id')
    with builder.contribution('custom'):
        opts.sys_fields(id={'name_long': 'Codice'})
    assert fields.get_attr('id') == {'type': 'uuid', 'name_long': 'Codice'}


def test_reset_removes_accumulated_configuration_without_creating_a_runtime_node():
    builder, _, pkg = source()
    opts = pkg.table('customer').options()
    opts.sys_fields(id=False)
    with builder.contribution('custom'):
        opts.reset('sys_fields')
        option = opts.sys_fields(draft=True)
    assert 'id' not in option.attr
    assert not any(node.node_tag == 'reset' for _, node in builder.source.query('#p,#n', deep=True))
    with pytest.raises(ValueError, match='unknown option'):
        opts.reset('typo')


def test_package_source_exports_the_declared_table():
    builder, _, pkg = source()
    pkg.table('customer').column('id', dtype='L')
    model = resolve_model(builder)
    assert len(model.tables) == 1
    table = next(iter(model.tables.values()))
    physical = SqlMigrationRenderer(builder).render()['root']['schemas']
    assert physical[table.physical_schema]['tables'][table.physical_name]['columns']['id']['attributes']['dtype'] == 'L'


def test_direct_declarations_also_work_on_legacy_schema_tables():
    builder = SqlBuilder()
    table = builder.source.db('d').schemas().schema('public').tables().table('customer', pkey='id')
    table.column('id', dtype='L')
    assert resolve_model(builder).table('public.customer').pkey == ('id',)


def test_group_handles_route_to_the_table_with_order_and_explicit_overrides():
    builder, _, pkg = source()
    table = pkg.table('customer')
    group = table.colgroup('address', name_long='Indirizzo', col_dtype='T', col_size=':80')
    first = group.column('street')
    second = group.column('city', size=':40')
    assert first.get_attr('group') == 'address.001'
    assert second.get_attr('group') == 'address.002'
    assert second.get_attr('size') == ':40'
    assert second.get_attr('dtype') == 'T'
    assert group.column('city') is second
    assert second.get_attr('size') == ':40'
    assert not group.value
    builder.validate_model()
    with pytest.raises(ValueError, match='conflicting'):
        table.colgroup('address', name_long='Different')
    with pytest.raises(ValueError, match='unknown column default'):
        table.colgroup('bad', col_dtypo='T')
