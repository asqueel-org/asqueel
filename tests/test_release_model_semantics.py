"""Contracts added on the path from package source to complete migration JSON."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer, PostgresCompiler, UnsupportedFeatureError
from asqueel.model import resolve_model
from asqueel.model_codec import model_from_json, model_to_json
from asqueel.validation import validate_value


def source():
    b = SqlDatabaseConfig()
    pkg = b.source.db('example').packages().package('sales')
    return b, pkg


def test_custom_types_forward_fk_inference_inverse_and_application_sql_actions():
    b, pkg = source()
    pkg.options().type('money', dtype='N', size='14,2')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('amount', 'money')
    invoice.column('customer_id').relation('customer.id', inverse='invoices', one_one=True,
        on_delete='raise', on_delete_sql='set_null')
    pkg.table('customer', pkey='id').column('id', 'C', size='22')
    m = resolve_model(b)
    assert m.table('invoice').columns['customer_id'].dtype == 'C'
    assert m.table('invoice').columns['customer_id'].attributes['size'] == '22'
    assert m.table('invoice').columns['amount'].attributes['size'] == '14,2'
    assert m.table('customer').relations['invoices'].kind == 'inverse'
    r = m.table('invoice').relations['customer_id']
    assert r.attributes['x_app_on_delete'] == 'raise'
    assert r.attributes['on_delete'] == 'SET NULL'
    physical = SqlMigrationRenderer(b).render()['root']['schemas']['public']['tables']['sales_invoice']
    assert not physical['columns']['customer_id']['attributes'].get('unique')
    assert next(iter(physical['relations'].values()))['attributes']['on_delete'] == 'SET NULL'
    with pytest.raises(UnsupportedFeatureError, match='write execution providers'):
        PostgresCompiler(m).insert('invoice', {'id': 1})


def test_weak_nonunique_relations_have_no_foreign_key_and_keep_indexes():
    b, pkg = source()
    pkg.table('target').column('code', 'T')
    pkg.table('child').column('target_code').weak_relation('target.code', inverse='children')
    m = resolve_model(b)
    assert m.table('child').relations['target_code'].kind == 'weak'
    tables = SqlMigrationRenderer(b).render()['root']['schemas']['public']['tables']
    assert not tables['sales_child']['relations']
    assert tables['sales_child']['indexes'] and tables['sales_target']['indexes']
    with pytest.raises(UnsupportedFeatureError, match='unique key'):
        PostgresCompiler(m).select('child', '@target_code.code')


def test_composite_primary_key_is_not_a_stored_column():
    b, pkg = source()
    t = pkg.table('line', pkey='identity')
    t.column('invoice_id', 'L')
    t.column('position', 'I')
    t.compositeColumn('identity', 'invoice_id,position')
    m = resolve_model(b)
    assert m.table('line').pkey == ('invoice_id', 'position')
    physical = SqlMigrationRenderer(b).render()['root']['schemas']['public']['tables']['sales_line']
    assert set(physical['columns']) == {'invoice_id', 'position'}
    assert physical['attributes']['pkeys'] == 'invoice_id,position'


def test_partial_index_cannot_silently_replace_a_required_full_index():
    b, pkg = source()
    t = pkg.table('item')
    t.column('code', 'T', indexed=True)
    t.index(columns='code', where='code IS NOT NULL')
    with pytest.raises(UnsupportedFeatureError, match='does not cover'):
        SqlMigrationRenderer(b).render()


def test_validation_embedding_and_explicit_form_match_and_remain_detached():
    b, pkg = source()
    t = pkg.table('item')
    t.column('a', 'T', validate_len='2:5', validate_len_error='Length', validate_case='upper')
    c = t.column('b', 'T')
    c.validation(len='2:5', messages={'len': 'Length'})
    c.normalize(case='upper')
    m = resolve_model(b)
    assert m.table('item').columns['a'].declarations == m.table('item').columns['b'].declarations
    assert model_from_json(model_to_json(m)) == m
    assert validate_value('èé', {'len': '2:5'}) == ()
    assert validate_value(None, {'notnull': True, 'len': '2:5'}) == ('notnull',)
    with pytest.raises(ValueError, match='authoritative server'):
        validate_value('alice', {'nodup': True})
    with pytest.raises(ValueError, match='Unknown validation'):
        t.column('bad', 'T', validate_lne=8)
    with pytest.raises(UnsupportedFeatureError, match='write execution providers'):
        PostgresCompiler(m).insert('item', {'a': 'abc'})


def test_virtual_relation_alias_and_python_provider_are_model_data_only():
    b, pkg = source()
    pkg.table('customer', pkey='id').column('id', 'L')
    pkg.table('customer').column('name', 'T')
    t = pkg.table('invoice')
    t.column('customer_id', 'L')
    t.virtualRelation('customer', table='sales.customer', condition='$customer_id = #THIS.id', one_one=True)
    t.aliasColumn('customer_name', '@customer.name')
    t.pyColumn('computed', method='invoice.total@1', required_columns=['customer_id'])
    m = resolve_model(b)
    assert m.table('invoice').columns['customer_name'].alias_target == ('sales.customer', 'name')
    assert m.table('invoice').columns['computed'].attributes['method'] == 'invoice.total@1'
    with pytest.raises(UnsupportedFeatureError, match='virtual navigation'):
        PostgresCompiler(m).select('invoice', '$customer_name')
    with pytest.raises(UnsupportedFeatureError, match='pyColumn'):
        PostgresCompiler(m).select('invoice', '$computed')
    assert model_from_json(model_to_json(m)) == m


def test_nested_metadata_is_immutable_and_preserves_list_semantics():
    b, pkg = source()
    t = pkg.table('item')
    original = ['first']
    t.column('value', 'T', metadata={'ui': {'choices': original}})
    m = resolve_model(b)
    original.append('later')
    data = m.table('item').columns['value'].attributes['metadata']['ui']
    assert data['choices'] == ['first']
    with pytest.raises(TypeError):
        data['choices'].append('bad')
    with pytest.raises(TypeError):
        data['choices'][0] = 'bad'
    assert model_from_json(model_to_json(m)) == m


def test_expanded_legacy_export_cannot_be_mistaken_for_an_executable_runtime():
    from tests.test_release_invoice_migration import invoice_source
    model = resolve_model(invoice_source())
    with pytest.raises(UnsupportedFeatureError, match='legacy runtime/compiler providers'):
        PostgresCompiler(model)
