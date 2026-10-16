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
    with pytest.raises(UnsupportedFeatureError, match='write execution'):
        PostgresCompiler(m).insert('invoice', {'id': 1})


def test_validation_embedding_and_explicit_form_match_and_remain_detached():
    b, pkg = source()
    t = pkg.table('item')
    t.column('a', 'T', validate_len='2:5', validate_len_error='Length', validate_case='U')
    c = t.column('b', 'T')
    c.validation(len='2:5', len_error='Length', case='U')
    m = resolve_model(b)
    assert m.table('item').columns['a'].declarations == m.table('item').columns['b'].declarations
    assert model_from_json(model_to_json(m)) == m
    rules = m.table('item').columns['a'].validations
    assert type(rules) is dict
    assert rules == {'len': '2:5', 'len_error': 'Length', 'case': 'U'}
    rules['case'] = 'lower'
    assert m.table('item').columns['a'].validations['case'] == 'U'
    assert validate_value('èé', {'len': '2:5'}) == ()
    assert validate_value(None, {'notnull': True, 'len': '2:5'}) == ('notnull',)
    with pytest.raises(ValueError, match='authoritative server'):
        validate_value('alice', {'nodup': True})
    t.column('opaque', 'T', validate_lne=8)
    assert resolve_model(b).table('item').columns['opaque'].validations == {'lne': 8}
    with pytest.raises(UnsupportedFeatureError, match='write execution'):
        PostgresCompiler(m).insert('item', {'a': 'abc'})
