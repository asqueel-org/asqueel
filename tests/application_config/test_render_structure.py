"""Source-to-object boundary: flat attributes, resolvers, isolation and publication."""
import pytest
from genro_bag.resolvers import BagCbResolver, EnvResolver

from asqueel import SqlDatabaseConfig
from asqueel.configuration import _owned_handler, build_database
from asqueel.model import resolve_model


def recipe():
    source = SqlDatabaseConfig()
    root = source.source.db('invoice', implementation='sqlite')
    root.connection('main', database=':memory:')
    packages = root.packages()
    sales = packages.package('invc', sqlschema='main', sqlprefix=True)
    adm = packages.package('adm', sqlschema='main', sqlprefix=False)
    packages.package('empty', sqlschema='main')
    customer = sales.table('customer', pkey='id', name_long='Cliente')
    customer.column('id', dtype='L')
    customer.column('account_name', validate_notnull=True, validate_len='2:40')
    invoice = sales.table('invoice', pkey='id', sqlname='invoices')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('invc.customer.id', relation_name='invoices')
    invoice.column('user_id', dtype='L').relation('adm.user.id')
    adm.table('user', pkey='id').column('id', dtype='L')
    return source, root, customer


def test_render_resolves_flat_values_and_detaches_structural_reads(monkeypatch):
    import sqlite3
    monkeypatch.setattr(sqlite3, 'connect', lambda *a, **k: pytest.fail('Render opened a connection'))
    monkeypatch.setenv('INVOICE_COLOR', 'blue')
    calls = []
    def length():
        calls.append('len')
        return '3:40'
    source, root, customer = recipe()
    column = customer.column('label', default=EnvResolver('INVOICE_COLOR'),
                             validate_len=BagCbResolver(length))
    # Unselected administrative connections must not be evaluated as model nodes.
    root.connection('archive', database=BagCbResolver(lambda: pytest.fail('Unused connection read')))
    assert 'validate_len' in column.attr
    assert column.value is None or column.value.get_node('validation') is None
    owned = _owned_handler(source)
    assert calls == []
    assert owned.builder is not source
    db = source.render()
    try:
        handle = db.table('invc.customer').column('label')
        assert handle.attributes['default'] == 'blue'
        assert handle.validations == {'len': '3:40'}
        assert calls
        count = len(calls)
        monkeypatch.setenv('INVOICE_COLOR', 'red')
        column.attr['default'] = 'green'
        db.config.builder.source.get_node('db.packages.invc.tables.customer.columns.label').attr['default'] = 'yellow'
        assert handle.attributes['default'] == 'blue'
        assert handle.dtype == 'T'
        assert handle.attributes.get('missing') is None
        assert handle.validations == {'len': '3:40'}
        assert len(calls) == count
        assert db.table('invc.invoice').model.column('@customer_id.id') is db.table('invc.customer').column('id')
        assert db.table('invc.customer').model is db.model.table('invc.customer')
        assert not db.model.package('empty').tables
        assert {t.sqlschema for t in db.model.tables.values()} == {'main'}
        assert db.model.table('invc.invoice').sqlname == 'invoices'
        assert 'archive' not in db.model.obj.attributes
    finally:
        db.closeConnection()


def test_callback_cache_semantics_are_owned_by_existing_resolver():
    source, _, customer = recipe()
    calls = []
    def value():
        calls.append(1)
        return 'fixed'
    resolver = BagCbResolver(value, cache_time=-1)
    customer.column('value', default=resolver, onDeleted=resolver)
    db = build_database(source)
    try:
        col = db.table('invc.customer').column('value')
        assert col.attributes['default'] == col.attributes['onDeleted'] == 'fixed'
        assert calls == [1]  # one shared resolver with its own permanent cache
    finally:
        db.closeConnection()


def test_render_defaults_follow_composition_and_failure_publishes_nothing():
    base, _, _ = recipe()
    overlay = SqlDatabaseConfig()
    table = overlay.source.db('invoice').packages().package('invc').table('customer')
    table.column('account_name', comment='red')
    db = build_database(overlay, parents=[base])
    try:
        assert db.table('invc.customer').attributes['name_long'] == 'Cliente'
        assert db.table('invc.customer').column('account_name').validations == {'notnull': True, 'len': '2:40'}
        assert db.table('invc.customer').column('account_name').attributes['comment'] == 'red'
        assert 'name_long' not in table.attr
    finally:
        db.closeConnection()
    broken, _, customer = recipe()
    customer.column('missing_id', dtype='L').relation('missing.table.id')
    with pytest.raises(ValueError):
        broken.render()
    assert not broken.materialized


@pytest.mark.parametrize('explicit_first', [True, False])
def test_validation_spellings_share_contribution_order(explicit_first):
    source, _, customer = recipe()
    column = customer.column('code')
    if explicit_first:
        column.validation(len='2:4')
    else:
        customer.column('code', validate_len='2:4')
    with source.contribution('later'):
        if explicit_first:
            customer.column('code', validate_len='3:8')
        else:
            column.validation(len='3:8')
    assert resolve_model(source).table('invc.customer').columns['code'].validations == {'len': '3:8'}


def test_removed_metadata_forms_are_not_part_of_source_grammar():
    source, root, customer = recipe()
    for kwargs in ({'metadata': {'ui': {'color': 'red'}}}, {'x_ui': {'color': 'red'}}):
        with pytest.raises(ValueError, match="Element 'column' does not accept"):
            customer.column('label', **kwargs)
    with pytest.raises(AttributeError):
        root.options().metadata('ui', {'color': 'red'})
    assert 'metadata' not in source._class_schema.keys()
