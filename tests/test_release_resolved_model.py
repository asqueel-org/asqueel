import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from asqueel.model_codec import model_to_json, model_from_json
from asqueel.projection import to_physical_builder


def recipe():
    builder = SqlDatabaseConfig()
    db = builder.source.db('invoice', name_long='Invoice DB')
    db.schemas().schema('sales', sqlname='billing', name_long='Sales')
    db.schemas().schema('empty')
    pkg = db.packages().package('invc', sqlschema='sales')
    pkg.table('customer', pkey='id', caption_field='name').column('id', 'L')
    pkg.table('customer').column('name', 'T')
    return builder, db, pkg


def test_schema_and_package_objects_preserve_identity_mapping_and_empty_sections():
    builder, db, pkg = recipe()
    db.packages().package('unused', sqlschema='empty', sqlprefix=False)
    model = resolve_model(builder)
    assert model.schemas['sales'].physical_name == 'billing'
    assert model.packages['invc'].sqlschema == 'sales'
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
    other = db.packages().package('other', sqlschema='sales', sqlprefix=False)
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
    physical = SqlMigrationRenderer(builder).render()['root']['schemas']['billing']['tables']['invc_invoice']
    assert '__record_pointer' not in physical['columns']
    assert 'id' in physical['columns']
