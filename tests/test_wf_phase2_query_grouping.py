"""Phase 2 contract — GROUP BY and HAVING belong to SELECT only (R15–R22, R28–R30, D4/D5/D8/D10)."""
import pytest

from asqueel.contracts import UnsupportedFeatureError

from tests import query_completion_support as support

shop = support.shop


@pytest.mark.parametrize('option', [{'group_by': '$customer_id'}, {'having': 'COUNT(*) > 1'}])
def test_query_write_terminals_reject_grouping(shop, option):
    with pytest.raises(UnsupportedFeatureError, match='only in a SELECT'):
        shop.query(**option).sql_delete()
    with pytest.raises(UnsupportedFeatureError, match='only in a SELECT'):
        shop.query(**option).sql_update({'note': 'x'})
    assert len(shop.ids()) > 0
