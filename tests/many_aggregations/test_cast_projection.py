"""Only outer AS names a projection; CAST's AS stays inside its expression."""
from decimal import Decimal
from xml.etree import ElementTree as ET

from genro_bag import Bag
import pytest

from .test_contracts import execute, json_value, query


CASES = [
    ('CAST($total AS NUMERIC)', ['CAST__total_AS_NUMERIC_'], [10]),
    ('CAST($id AS NUMERIC), CAST($total AS NUMERIC)',
     ['CAST__id_AS_NUMERIC_', 'CAST__total_AS_NUMERIC_'], [1, 10]),
    ('CAST($id AS NUMERIC) AS invoice_id, CAST($total AS NUMERIC) AS amount',
     ['invoice_id', 'amount'], [1, 10]),
    ('CAST(CAST($total AS NUMERIC) AS NUMERIC)',
     ['CAST_CAST__total_AS_NUMERIC__AS_NUMERIC_'], [10]),
    ('CAST($id AS NUMERIC) AS value, CAST($total AS NUMERIC) AS value', ['value'], [10]),
]


@pytest.mark.parametrize('selection, expected_names, expected_values', CASES)
def test_cast_projection_keeps_columns_names_and_values(model, connection, selection, expected_names, expected_values):
    q = model.table('app.invoice').query(selection, where='$id=:id', id=1)
    names, rows = execute(connection, q)
    assert names == expected_names
    assert rows == [tuple(expected_values)]
    assert [column.name for column in q.compiled.columns] == names


@pytest.mark.parametrize('selection, expected', [
    ('CAST($id AS NUMERIC), CAST($total AS NUMERIC)', {}),
    ('CAST($id AS NUMERIC) AS invoice_id, CAST($total AS NUMERIC) AS amount',
     {'"invoice_id"': 'CAST($id AS NUMERIC)', '"amount"': 'CAST($total AS NUMERIC)'}),
])
def test_alias_dictionary_records_only_outer_as(model, selection, expected):
    plan = model.compiler.plan_select('app.invoice', columns=selection)
    assert plan.aliasDict == expected


def test_two_casts_in_json_use_the_same_names_as_query(model, connection):
    selection = 'CAST($id AS NUMERIC), CAST($total AS NUMERIC)'
    names, values = execute(connection, model.table('app.invoice').query(
        selection, where='$customer_id=:customer', customer=1))
    _, rows = execute(connection, query(model, f'@invoices.aggr(to_json({selection}) AS invoices)'))
    assert names == ['CAST__id_AS_NUMERIC_', 'CAST__total_AS_NUMERIC_']
    assert json_value(rows[0][0]) == [dict(zip(names, row)) for row in values]


@pytest.mark.parametrize('selection, expected_names, expected_values', CASES)
def test_casts_in_xml_need_no_explicit_alias(model, connection, xml_backend,
                                           selection, expected_names, expected_values):
    names, rows = execute(connection, query(model, f'@invoices.aggr(to_xml({selection}) AS invoices)'))
    assert names == ['invoices']
    root = ET.fromstring(rows[0][0])
    assert [node.tag for node in root] == ['r_0', 'r_1', 'r_2', 'r_3']
    # Bag preserves generated names through _tag when XML tag normalization differs.
    assert [node.get('_tag', node.tag) for node in root[0]] == expected_names
    assert [Decimal(node.text) for node in root[0]] == expected_values
    assert [node.get('_T') for node in root[0]] == ['N'] * len(expected_names)


def test_two_casts_xml_roundtrip_restores_generated_aliases(model, connection, xml_backend):
    module = pytest.importorskip('gnr.core.gnrclasses', reason='Optional real GenroPy catalog for typed Bag round-trip')
    _, rows = execute(connection, query(model,
        '@invoices.aggr(to_xml(CAST($id AS NUMERIC), CAST($total AS NUMERIC)) AS invoices)'))
    bag = Bag.from_xml(rows[0][0], legacy_mode=True, catalog=module.GnrClassCatalog())
    for index in range(4):
        row = bag.get_item(f'r_{index}')
        assert [node.label for node in row] == ['CAST__id_AS_NUMERIC_', 'CAST__total_AS_NUMERIC_']
        assert [node.value for node in row] == [Decimal(index + 1), Decimal((index + 1) * 10)]
        assert all(type(node.value) is Decimal for node in row)
