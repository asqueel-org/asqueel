"""Declaration-only contracts: no live-model or provider construction."""
from pathlib import Path
import importlib.util

import pytest
from asqueel import SqlDatabaseConfig, SqlBuilder, SqlMigrationRenderer, UnsupportedFeatureError
from asqueel.configuration import _copy_recipe, _owned_handler
from asqueel.option_elements import TABLE_OPTIONS


def source():
    b = SqlDatabaseConfig()
    db = b.source.db('grammar')
    table = db.packages().package('app').table('item')
    return b, db, table


def complete_example(**kwargs):
    path = Path(__file__).parents[1] / 'examples/model_grammar/configure.py'
    spec = importlib.util.spec_from_file_location('grammar_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.source(**kwargs)


def test_invoice_example_is_buildable_without_expansion_or_provider_resolution(monkeypatch):
    from asqueel import model, model_expansion
    def forbidden(*args, **kwargs):
        pytest.fail('Source grammar must not resolve objects or expand options')
    monkeypatch.setattr(model, 'resolve_model', forbidden)
    monkeypatch.setattr(model_expansion, 'expand_options', forbidden)
    b = complete_example()
    nodes = [node for _, node in b.source.query('#p,#n', deep=True)]
    assert not any(node.node_tag == 'column' and node.get_attr('name') in (
        'id', '__ins_ts', 'hierarchical_pkey', 'filepath', '__version') for node in nodes)
    assert b.validate_source() == []
    clone = _copy_recipe(b)
    assert clone.source.get_node('db').get_attr('name') == 'test_invoice_pg'
    _owned_handler(b)  # Configuration composition is also declaration-only.


@pytest.mark.parametrize(('tag', 'kwargs'), [
    ('hierarchical', {'columns': ['code']}), ('auto_counter', {}),
    ('relative_index', {'relation': 'owner_id'}), ('dynamic_fields', {}),
    ('record_hash', {}), ('full_update', {}),
    ('audit', {'mode': 'lazy'}),
    ('system_records', {'records': {'a': {'title': 'A'}}}),
    ('protection', {}), ('diagnostics', {}), ('release', {'handlers': {'1': 'app.upgrade'}}),
    ('partition', {'name': 'org', 'field': 'org_id', 'value': 'organization'}),
    ('tenant', {}),
    ('retention', {'field': 'created', 'days': 30}),
    ('broadcast', {}), ('archive', {}),
    ('enabled_when', {'preference': 'enabled'}),
    ('attachments', {'master': 'app.item'}),
    ('numbering', {'field': 'code'}),
])
def test_option_signatures_are_closed_and_scoped(tag, kwargs):
    b, db, table = source()
    node = getattr(table.options(), tag)(**kwargs)
    assert node.node_tag == tag
    with pytest.raises(ValueError, match='does not accept'):
        getattr(table.options(), tag)(**kwargs, typoo=True)
    with pytest.raises(ValueError, match='not available'):
        getattr(db.options(), tag)(**kwargs)
    b.validate_source()


def test_merge_disable_reenable_and_reset_keep_explicit_source_values():
    b, _, table = source()
    opts = table.options()
    opts.audit('lazy')
    opts.numbering('code', parameters={'prefix': 'A'})
    opts.numbering('code', parameters={'yearly': True})
    assert table.value.get_node('options.numbering_code').get_attr('parameters') == {'prefix': 'A', 'yearly': True}
    with b.contribution('disable'):
        opts.audit(False)
    b.validate_source()
    with b.contribution('reenable'):
        opts.audit(enabled=True)
    audit = table.value.get_node('options.audit')
    assert audit.get_attr('mode') == 'lazy'
    opts.reset('audit')
    with pytest.raises(ValueError, match='required'):
        opts.audit(enabled=True)
    opts.audit('full')
    assert _copy_recipe(b).validate_source() == []


def test_named_options_are_independent_and_broadcast_accepts_positional_columns():
    b, _, table = source()
    opts = table.options()
    one = opts.partition('one', field='one_id', value='one')
    two = opts.partition('two', field='two_id', value='two')
    assert one is not two
    assert opts.numbering('first') is not opts.numbering('second')
    assert opts.broadcast('a', 'b').get_attr('columns') == ['a', 'b']
    b.validate_source()


@pytest.mark.parametrize(('tag', 'kwargs'), [
    ('audit', {'mode': 'typo'}),
    ('audit', {}),
    ('hierarchical', {'columns': [{'name': 'code', 'size': 10}]}),
    ('hierarchical', {'columns': [{'name': 'code', 'unique': 'yes'}]}),
    ('hierarchical', {'depth': True}), ('hierarchical', {'depth': 0}),
    ('retention', {'field': 'date', 'days': -1}),
    ('retention', {'field': 'date', 'days': True}),
    ('system_records', {'records': {'a': lambda: None}}),
    ('release', {'handlers': {1: 'app.upgrade'}}),
    ('numbering', {'field': 'code', 'parameters': {'bad': float('nan')}}),
    ('protection', {'rules': [lambda: None]}), ('dynamic_fields', {'source': 'app.t.col'}),
])
def test_invalid_payloads_are_rejected_without_instantiating_providers(tag, kwargs):
    _, _, table = source()
    with pytest.raises(ValueError):
        getattr(table.options(), tag)(**kwargs)


def test_column_dynamic_fields_has_its_own_payload_and_no_implicit_expansion():
    b, _, table = source()
    col = table.column('data', 'X')
    node = col.dynamic_fields(source='app.template.fields')
    assert node.get_attr('source') == 'app.template.fields'
    with pytest.raises(ValueError, match='not templates'):
        col.dynamic_fields(templates={})
    b.validate_source()
    node.attr['typo'] = True
    with pytest.raises(ValueError, match='does not accept'):
        b.validate_source()


def test_grammar_export_and_source_json_preserve_declarations(tmp_path):
    b, _, table = source()
    table.options().hierarchical(columns=[{'name': 'code', 'unique': True}])
    path = tmp_path / 'grammar.json'
    SqlBuilder.to_grammar(path)
    text = path.read_text()
    assert all('"' + tag + '"' in text for tag in TABLE_OPTIONS)
    from genro_bag import Bag
    parsed = Bag.from_json(b.source.to_json())
    assert parsed.get_node('db.packages.app.tables.item.options.hierarchical').get_attr('columns') == [{'name': 'code', 'unique': True}]


def test_declaration_only_options_cannot_be_silently_omitted_from_migration():
    b, _, table = source()
    table.column('id', 'L')
    table.options().attachments(master='app.parent')
    with pytest.raises(UnsupportedFeatureError, match='declaration-only'):
        SqlMigrationRenderer(b).render()


def test_removed_declarations_are_not_in_the_grammar(tmp_path):
    b, db, table = source()
    for owner, name in ((db.options(), 'context'), (table.column('id'), 'generation'),
                        (table.options(), 'behavior'), (table.options(), 'pkey_from'),
                        (db.options(), 'macro'), (table.parent_node.parent_node.options(), 'macro'),
                        (table.column('id'), 'normalize')):
        with pytest.raises((AttributeError, ValueError)):
            getattr(owner, name)('invented')
    path = tmp_path / 'grammar.json'
    SqlBuilder.to_grammar(path)
    import json
    grammar = json.loads(path.read_text())
    assert '"context"' not in json.dumps(grammar)
    assert '"generation"' not in json.dumps(grammar)
    assert '"behavior"' not in json.dumps(grammar)
    assert '"provider"' not in json.dumps(grammar)
    assert '"pkey_from"' not in json.dumps(grammar)
    assert '"macro"' not in json.dumps(grammar)
    assert '"normalize"' not in json.dumps(grammar)


@pytest.mark.parametrize('name', ['context', 'generation', 'behavior', 'pkey_from', 'macro', 'normalize'])
def test_old_source_nodes_cannot_silently_survive_composition(name):
    b, db, _ = source()
    opts = db.options()
    opts.value = type(b.source)(builder=b)
    opts.value.set_item(name, None, node_tag=name)
    with pytest.raises(ValueError, match='removed'):
        b.validate_source()


@pytest.mark.parametrize(('tag', 'kwargs'), [
    ('audit', {'mode': 'lazy'}), ('tenant', {}),
    ('retention', {'field': '__ins_ts', 'days': 60}),
    ('broadcast', {'columns': 'objtype'}), ('archive', {}),
    ('enabled_when', {'preference': 'adm.dev.connection_log_enabled'}),
    ('attachments', {'master': 'adm.htmltemplate'}), ('numbering', {'field': 'inv_number'}),
])
def test_legacy_options_reject_provider_bindings(tag, kwargs):
    b, _, table = source()
    node = getattr(table.options(), tag)(**kwargs)
    b.validate_source()
    with pytest.raises(ValueError, match='does not accept'):
        getattr(table.options(), tag)(**kwargs, provider='app.handler')
    node.attr['provider'] = 'app.handler'
    with pytest.raises(ValueError, match='provider removed'):
        b.validate_source()


def test_existing_resolvers_survive_build_clone_and_composition_without_running(monkeypatch):
    from genro_bag import BagResolver
    from genro_bag.resolvers import BagCbResolver, EnvResolver
    def forbidden(*args, **kwargs):
        pytest.fail('Resolvers must stay deferred while building the source')
    monkeypatch.setattr(EnvResolver, 'load', forbidden)
    b = complete_example(current_state=forbidden)
    # Exercise a calculated configuration value, not a per-write default.
    b.source.get_node('db.packages.invc.tables.invoice').column(
        'date', default=BagCbResolver(forbidden))
    for builder in (b, _copy_recipe(b), _owned_handler(b).builder):
        assert builder.validate_source() == []
        invoice = builder.source.get_node('db.packages.invc.tables.invoice')
        assert isinstance(invoice.value.get_node('columns.date').get_attr('default'), BagCbResolver)
        assert isinstance(invoice.value.get_node('options.partition_customer_state').get_attr('value'), BagResolver)
        assert isinstance(builder.source.get_node('db.connection').get_attr('password'), EnvResolver)
    # Ordinary Python callbacks must be wrapped in the existing resolver.
    with pytest.raises(ValueError, match='BagResolver'):
        b.source.get_node('db.packages.invc.tables.customer').options().partition(
            'invalid', field='state', value=forbidden)


def test_encryption_rejects_provider_in_calls_and_imported_source():
    b, _, table = source()
    column = table.column('secret')
    node = column.encryption(mode='R')
    b.validate_source()
    with pytest.raises(ValueError, match='does not accept'):
        column.encryption(mode='R', provider='app.crypto')
    node.attr['provider'] = 'app.crypto'
    with pytest.raises(ValueError, match='provider removed'):
        b.validate_source()


def test_review_example_uses_only_real_inventory_tables():
    import json
    b = complete_example()
    root = Path(__file__).parents[1]
    inventory = json.loads((root / 'docs/design/evidence/test-invoice-model-inventory.json').read_text())
    # The checked-in coverage table is derived from the inventory, including inherited tables.
    coverage = (root / 'docs/design/43-test-invoice-model-coverage.md').read_text()
    assert set(inventory['model_files_per_package']) == {'sys', 'adm', 'invc'}
    for _, node in b.source.query('#p,#n', deep=True):
        if node.node_tag == 'table':
            package = node.parent_node.parent_node.get_attr('name')
            assert f'| {package}.{node.get_attr("name")} |' in coverage


def test_alias_table_is_deferred_but_virtual_relation_remains():
    b, _, table = source()
    with pytest.raises((AttributeError, ValueError)):
        table.aliasTable('customer', relation_path='@invoice_id.@customer_id')
    table.virtualRelation('customer', relation='@invoice_id.@customer_id')
    for builder in (b, _copy_recipe(b), _owned_handler(b).builder):
        assert builder.validate_source() == []
        node = builder.source.get_node('db.packages.app.tables.item.virtualRelation_customer')
        assert node.get_attr('relation') == '@invoice_id.@customer_id'
