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


def complete_example():
    path = Path(__file__).parents[1] / 'examples/model_grammar/configure.py'
    spec = importlib.util.spec_from_file_location('grammar_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.source()


def test_complete_catalog_is_buildable_without_expansion_or_provider_resolution(monkeypatch):
    from asqueel import model, model_expansion
    def forbidden(*args, **kwargs):
        pytest.fail('Source grammar must not resolve objects or expand options')
    monkeypatch.setattr(model, 'resolve_model', forbidden)
    monkeypatch.setattr(model_expansion, 'expand_options', forbidden)
    b = complete_example()
    nodes = [node for _, node in b.source.query('#p,#n', deep=True)]
    assert set(TABLE_OPTIONS) <= {node.node_tag for node in nodes}
    assert not any(node.node_tag == 'column' and node.get_attr('name') in (
        'id', '__ins_ts', 'hierarchical_pkey', 'filepath', '__version') for node in nodes)
    assert b.validate_source() == []
    clone = _copy_recipe(b)
    assert clone.source.to_xml() == b.source.to_xml()
    _owned_handler(b)  # Configuration composition is also declaration-only.


@pytest.mark.parametrize(('tag', 'kwargs'), [
    ('behavior', {'reference': 'app.item'}),
    ('pkey_from', {'columns': ['a', 'b']}),
    ('hierarchical', {'columns': ['code']}), ('auto_counter', {}),
    ('relative_index', {'relation': 'owner_id'}), ('dynamic_fields', {}),
    ('record_hash', {}), ('full_update', {}),
    ('audit', {'mode': 'lazy', 'provider': 'app.audit'}),
    ('system_records', {'records': {'a': {'title': 'A'}}}),
    ('protection', {}), ('diagnostics', {}), ('release', {'handlers': {'1': 'app.upgrade'}}),
    ('partition', {'name': 'org', 'field': 'org_id', 'context': 'organization'}),
    ('tenant', {'context': 'tenant', 'provider': 'app.tenant'}),
    ('retention', {'field': 'created', 'days': 30, 'provider': 'app.retention'}),
    ('broadcast', {'provider': 'app.events'}), ('archive', {'provider': 'app.archive'}),
    ('enabled_when', {'preference': 'enabled', 'provider': 'app.preferences'}),
    ('attachments', {'master': 'app.item', 'provider': 'app.storage'}),
    ('numbering', {'field': 'code', 'provider': 'app.counter'}),
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
    opts.audit('lazy', provider='app.audit')
    opts.numbering('code', provider='app.numbering', parameters={'prefix': 'A'})
    opts.numbering('code', parameters={'yearly': True})
    assert table.value.get_node('options.numbering_code').get_attr('parameters') == {'prefix': 'A', 'yearly': True}
    with b.contribution('disable'):
        opts.audit(False)
    b.validate_source()
    with b.contribution('reenable'):
        opts.audit(enabled=True)
    audit = table.value.get_node('options.audit')
    assert audit.get_attr('mode') == 'lazy'
    assert audit.get_attr('provider') == 'app.audit'
    opts.reset('audit')
    with pytest.raises(ValueError, match='required'):
        opts.audit(enabled=True)
    opts.audit('full', provider='another.audit')
    assert _copy_recipe(b).validate_source() == []


def test_named_options_are_independent_and_broadcast_accepts_positional_columns():
    b, _, table = source()
    opts = table.options()
    one = opts.partition('one', field='one_id', context='one')
    two = opts.partition('two', field='two_id', context='two')
    assert one is not two
    assert opts.numbering('first', provider='app.first') is not opts.numbering('second', provider='app.second')
    assert opts.broadcast('a', 'b', provider='app.events').get_attr('columns') == ['a', 'b']
    b.validate_source()


@pytest.mark.parametrize(('tag', 'kwargs'), [
    ('audit', {'mode': 'typo', 'provider': 'app.audit'}),
    ('audit', {'mode': 'lazy'}), ('archive', {'provider': lambda: None}),
    ('archive', {'provider': 'app..invalid'}), ('pkey_from', {'columns': ['a', 'a']}),
    ('hierarchical', {'columns': [{'name': 'code', 'size': 10}]}),
    ('hierarchical', {'columns': [{'name': 'code', 'unique': 'yes'}]}),
    ('hierarchical', {'depth': True}), ('hierarchical', {'depth': 0}),
    ('retention', {'field': 'date', 'days': -1, 'provider': 'app.retention'}),
    ('retention', {'field': 'date', 'days': True, 'provider': 'app.retention'}),
    ('system_records', {'records': {'a': lambda: None}}),
    ('release', {'handlers': {1: 'app.upgrade'}}),
    ('numbering', {'field': 'code', 'provider': 'app.counter', 'parameters': {'bad': float('nan')}}),
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
    b = complete_example()
    path = tmp_path / 'grammar.json'
    SqlBuilder.to_grammar(path)
    text = path.read_text()
    assert all('"' + tag + '"' in text for tag in TABLE_OPTIONS)
    from genro_bag import Bag
    parsed = Bag.from_json(b.source.to_json())
    assert parsed.get_node('db.packages.invc.tables.invoice.options.audit').get_attr('provider') == 'accounting.audit'
    assert parsed.get_node('db.packages.invc.tables.product_type.options.hierarchical').get_attr('columns') == [{'name': 'code', 'unique': True}]


def test_declaration_only_options_cannot_be_silently_omitted_from_migration():
    b, _, table = source()
    table.column('id', 'L')
    table.options().attachments(master='app.parent', provider='app.storage')
    with pytest.raises(UnsupportedFeatureError, match='declaration-only'):
        SqlMigrationRenderer(b).render()
