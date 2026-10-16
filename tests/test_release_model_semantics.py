"""Contracts added on the path from package source to complete migration JSON."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer, UnsupportedFeatureError
from asqueel.model import resolve_model
from asqueel.model_codec import model_from_json, model_to_json
from asqueel.model_source import require_write_capabilities
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
    assert m.table('sales.invoice').columns['customer_id'].dtype == 'C'
    assert m.table('sales.invoice').columns['customer_id'].attributes['size'] == '22'
    assert m.table('sales.invoice').columns['amount'].attributes['size'] == '14,2'
    assert m.table('sales.customer').relations.get_node('@invoices').attr['joiner']['mode'] == 'M'
    r = m.table('sales.invoice').relations.get_node('@customer_id').attr['joiner']
    assert r['onDelete'] == 'raise'
    assert r['onDelete_sql'] == 'setnull'
    physical = SqlMigrationRenderer(b).render()['root']['schemas']['public']['tables']['sales_invoice']
    assert not physical['columns']['customer_id']['attributes'].get('unique')
    assert next(iter(physical['relations'].values()))['attributes']['on_delete'] == 'SET NULL'
    assert require_write_capabilities(m.table('sales.invoice')) is None


def test_validation_embedding_and_explicit_form_match_and_remain_detached():
    b, pkg = source()
    t = pkg.table('item')
    t.column('a', 'T', validate_len='2:5', validate_len_error='Length', validate_case='U')
    c = t.column('b', 'T')
    c.validation(len='2:5', len_error='Length', case='U')
    m = resolve_model(b)
    assert m.table('sales.item').columns['a'].validations == m.table('sales.item').columns['b'].validations
    rules = m.table('sales.item').columns['a'].validations
    assert type(rules) is dict
    assert rules == {'len': '2:5', 'len_error': 'Length', 'case': 'U'}
    rules['case'] = 'lower'
    assert m.table('sales.item').columns['a'].validations['case'] == 'U'
    assert validate_value('èé', {'len': '2:5'}) == ()
    assert validate_value(None, {'notnull': True, 'len': '2:5'}) == ('notnull',)
    with pytest.raises(ValueError, match='authoritative server'):
        validate_value('alice', {'nodup': True})
    t.column('opaque', 'T', validate_lne=8)
    assert resolve_model(b).table('sales.item').columns['opaque'].validations == {'lne': 8}
    with pytest.raises(UnsupportedFeatureError, match='write execution'):
        require_write_capabilities(m.table('sales.item'))


@pytest.mark.xfail(strict=True, reason='issue draft 2: the hierarchical DbModel has no JSON round trip')
def test_validation_model_survives_a_json_round_trip():
    b, pkg = source()
    t = pkg.table('item')
    t.column('a', 'T', validate_len='2:5', validate_len_error='Length', validate_case='U')
    m = resolve_model(b)
    assert model_from_json(model_to_json(m)) == m
