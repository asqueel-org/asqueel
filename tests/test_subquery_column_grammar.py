"""Legacy subQueryColumn signatures preserve source declarations."""
import pytest

from asqueel import SqlDatabaseConfig
from asqueel.configuration import _copy_recipe, _owned_handler
from asqueel.model import resolve_model
from asqueel.model_codec import model_from_json, model_to_json


@pytest.mark.parametrize('mode', [None, 'json', 'xml', 'sum'])
def test_subquery_column_keeps_legacy_defaults_and_later_query_contributions(mode):
    b = SqlDatabaseConfig()
    table = b.source.db('example').packages().package('invc').table('invoice')
    column = table.subQueryColumn('max_row_price', dtype='N', name_long='Max Row Price')
    assert column.get_attr('query') is None
    assert column.get_attr('mode') is None
    assert b.validate_source() == []
    query = {'table': 'invc.invoice_row', 'columns': 'MAX($unit_price)',
             'where': '$invoice_id=#THIS.id'}
    with b.contribution('definition'):
        table.subQueryColumn('max_row_price', query=query, mode=mode)
    for builder in (b, _copy_recipe(b), _owned_handler(b).builder):
        assert builder.validate_source() == []
        model = model_from_json(model_to_json(resolve_model(builder)))
        result = model.table('invc.invoice').columns['max_row_price']
        assert result.dtype == 'N'
        assert result.attributes['name_long'] == 'Max Row Price'
        assert result.attributes['query'] == query
        assert result.attributes.get('mode') == mode
        assert result.formula is None
