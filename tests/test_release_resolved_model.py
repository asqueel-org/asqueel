import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from asqueel.model_codec import model_to_json, model_from_json
from asqueel.projection import to_physical_builder


def recipe():
    builder = SqlDatabaseConfig()
    db = builder.source.db('invoice', name_long='Invoice DB')
    pkg = db.packages().package('invc', sqlschema='billing')
    pkg.table('customer', pkey='id', caption_field='name').column('id', 'L')
    pkg.table('customer').column('name', 'T')
    return builder, db, pkg


@pytest.mark.parametrize('joiner', [None, '_', '|', ''])
def test_legacy_textual_key_declaration_stays_distinct_from_sql_primary_key(joiner):
    builder, _, pkg = recipe()
    table = pkg.table('service', pkey='identifier',
                      pkey_columns='service_type,service_name', pkey_columns_joiner=joiner)
    table.column('identifier', size=':60')
    table.column('service_type', size=':30')
    table.column('service_name', size=':30')
    builder.validate_source()
    resolved = resolve_model(builder).table('invc.service')
    assert resolved.attributes['pkey_columns'] == 'service_type,service_name'
    assert resolved.attributes['pkey_columns_joiner'] == joiner
    assert resolved.pkey == ('identifier',)
    physical = SqlMigrationRenderer(builder).render()['root']['schemas']['billing']['tables']['invc_service']
    assert physical['attributes']['pkeys'] == 'identifier'
    assert 'pkey_columns' not in physical['attributes']
    assert 'pkey_columns_joiner' not in physical['attributes']


def test_schema_and_package_objects_preserve_identity_mapping_and_empty_sections():
    builder, db, pkg = recipe()
    db.packages().package('unused', sqlschema='empty', sqlprefix=False)
    model = resolve_model(builder)
    assert model.schemas['billing'].physical_name == 'billing'
    assert model.packages['invc'].sqlschema == 'billing'
    assert model.packages['unused'].tables == ()
    assert model.table('invc.customer').physical_name == 'invc_customer'
    assert model.table('invc.customer').physical_schema == 'billing'
    pkg.table('customer', name_long='Changed afterwards')
    assert 'name_long' not in model.table('invc.customer').attributes
    physical = SqlMigrationRenderer(to_physical_builder(model)).render()['root']
    assert set(physical['schemas']) == {'billing', 'empty'}
    assert 'invc_customer' in physical['schemas']['billing']['tables']


def test_metadata_options_do_not_propagate_and_model_round_trips_without_connections():
    builder, db, pkg = recipe()
    db.connection('main', database='invoice', password='secret-sentinel')
    db.options().metadata('ui', {'color': 'red'})
    pkg.options().metadata('ui', {'color': 'blue'})
    model = resolve_model(builder)
    assert model.table('invc.customer').options == {}
    with pytest.raises(TypeError):
        model.packages['invc'].options['metadata_ui'].attributes['values']['color'] = 'x'
    encoded = model_to_json(model)
    assert 'secret-sentinel' not in encoded
    assert model_from_json(encoded) == model


def test_package_requires_and_physical_collisions_are_loud():
    builder, db, pkg = recipe()
    pkg.options().requires('missing')
    with pytest.raises(ValueError, match='missing required'):
        resolve_model(builder)
    pkg.options().reset('requires')
    other = db.packages().package('other', sqlschema='billing', sqlprefix=False)
    other.table('invc_customer').column('id', 'L')
    with pytest.raises(ValueError, match='Duplicate physical table'):
        resolve_model(builder)


def test_system_field_expansion_is_repeatable_and_keeps_source_unexpanded():
    builder, _, pkg = recipe()
    table = pkg.table('invoice')
    table.options().sys_fields(user_upd=False, draft=True)
    first = resolve_model(builder)
    assert first == resolve_model(builder)
    assert builder.source['db.packages.invc.tables.invoice.columns'] is None
    resolved = first.table('invc.invoice')
    assert resolved.pkey == ('id',)
    assert resolved.columns['id'].dtype == 'A'
    assert resolved.columns['id'].attributes['size'] == '22'
    assert '__mod_user' not in resolved.columns
    assert resolved.columns['__is_draft'].dtype == 'B'
    assert resolved.columns['__record_pointer'].is_virtual
    for name in ('__ins_ts', '__mod_ts', '__del_ts'):
        assert resolved.columns[name].dtype == 'DHZ'
    physical = SqlMigrationRenderer(builder).render()['root']['schemas']['billing']['tables']['invc_invoice']
    assert '__record_pointer' not in physical['columns']
    assert 'id' in physical['columns']


@pytest.mark.parametrize(('implementation', 'default_schema'), [('postgresql', 'public'), ('sqlite', 'main')])
def test_schemas_are_deduced_from_packages_including_shared_empty_and_default(implementation, default_schema):
    builder = SqlDatabaseConfig()
    db = builder.source.db('d', implementation=implementation)
    packages = db.packages()
    packages.package('first', sqlschema='shared')
    packages.package('second', sqlschema='shared')
    packages.package('defaulted')
    assert builder.validate_source() == []
    assert builder.source.get_node('db.schemas') is None
    model = resolve_model(builder)
    assert set(model.schemas) == {'shared', default_schema}
    assert model.packages['first'].sqlschema == model.packages['second'].sqlschema == 'shared'
    assert model.packages['defaulted'].sqlschema == default_schema
    assert builder.source.get_node('db.schemas') is None
    physical = SqlMigrationRenderer(to_physical_builder(model)).render()['root']
    assert set(physical['schemas']) == {'shared', default_schema}


def test_package_source_rejects_the_superseded_explicit_schema_section():
    builder, db, _ = recipe()
    db.schemas().schema('billing')
    with pytest.raises(ValueError, match='remove the explicit schemas'):
        builder.validate_source()


def test_table_schema_override_uses_a_schema_deduced_from_another_package():
    builder, db, pkg = recipe()
    db.packages().package('archive', sqlschema='history')
    pkg.table('archived', sqlschema='history', pkey='id').column('id', 'L')
    assert resolve_model(builder).table('invc.archived').physical_schema == 'history'
    pkg.table('invalid', sqlschema='undeclared').column('id', 'L')
    with pytest.raises(ValueError, match='not derived from a package'):
        resolve_model(builder)
