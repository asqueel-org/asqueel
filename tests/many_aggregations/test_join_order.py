"""Ordered SQL string aggregation uses the existing child SELECT scopes."""
import pytest

from asqueel import build_database
from .conftest import source
from .test_contracts import execute, query


@pytest.mark.parametrize('order, expected', [
    ('$qty DESC, $id', '-,xx,zz,-'),
    ('@vat_id.rate DESC, $id DESC', '-,zz,-,xx'),
    ('$adjusted DESC', '-,zz,-,xx'),
])
def test_order_uses_unselected_columns_relations_and_formulas(model, connection, order, expected):
    names, rows = execute(connection, query(model,
        f"@invoices.order_by('{order}').aggr("
        "join($code, ',', '-') AS codes, count() AS n, sum($total) AS total)"))
    assert names == ['codes', 'n', 'total']
    assert rows == [(expected, 4, 100)]


@pytest.mark.parametrize('expression, expected', [
    ("join(upper($code), ';', '-') AS codes", 'XX;-;ZZ;-'),
    ("join(code, ',') AS codes", 'xx,,zz,'),
    ("join($adjusted, ',') AS codes", '25,45,65,85'),
    ("join(@vat_id.rate, ',') AS codes", '10,10,20,20'),
    ("join(CASE WHEN $id=1 THEN ' ' ELSE $code END, ',', '-') AS codes", ' ,-,zz,-'),
    ("join($code, ',', 'it''s empty') AS codes", "xx,it's empty,zz,it's empty"),
])
def test_join_expressions_and_placeholder(model, connection, expression, expected):
    names, rows = execute(connection, query(model, f'@invoices.aggr({expression})'))
    assert names == ['codes']
    assert rows == [(expected,)]


def test_join_child_bindings_do_not_mix_with_outer_or_order_formulas(model, connection):
    params = {'offset': 99, 'customer': 1}
    q = model.table('app.customer').query(
        "$id+:offset AS outer_value,"
        "@invoices.order_by('$adjusted_again DESC').aggr(join($adjusted, ',') AS amounts),"
        "@invoices.aggr(join($total+:offset, ',') AS external)",
        where='$id=:customer', sqlparams=params)
    compiled = q.compiled
    names, rows = execute(connection, q)
    assert names == ['outer_value', 'amounts', 'external']
    assert rows == [(100, '85,65,45,25', '109,119,129,139')]
    assert compiled.params['offset'] == 99
    assert {5, 7}.issubset(set(compiled.params.values()))
    assert q.compiled == compiled
    assert params == {'offset': 99, 'customer': 1}


@pytest.mark.parametrize('relation', ['large_invoices', 'above_customer'])
def test_virtual_join_base_order_and_override(model, connection, relation):
    names, rows = execute(connection, model.table('app.customer').query(
        f"$id,@{relation}.aggr(join($total, ',') AS ascending),"
        f"@{relation}.order_by('$id DESC').aggr(join($total, ',') AS descending)",
        order_by='$id DESC'))
    assert names == ['id', 'ascending', 'descending']
    assert rows == [(3, '', ''), (2, '', ''), (1, '20,30,40', '40,30,20')]


def test_to_one_prefix_then_many_join(model, connection):
    names, rows = execute(connection, model.table('app.invoice').query(
        "$id,@customer_id.@invoices.order_by('$id DESC').aggr(join($code, ',') AS codes)",
        order_by='$id'))
    assert names == ['id', 'codes']
    assert rows == [(1, ',zz,,xx'), (2, ',zz,,xx'), (3, ',zz,,xx'), (4, ',zz,,xx'), (5, '')]


def test_no_table_order_does_not_invent_a_fallback(backend, connection):
    config = source(backend, order_by=None)
    model = build_database(config)
    try:
        q = query(model, "@invoices.aggr(join($code, ',', '-') AS codes)")
        assert 'ORDER BY' not in q.compiled.sql
        names, rows = execute(connection, q)
    finally:
        model.closeConnection()
    assert names == ['codes']
    assert sorted(rows[0][0].split(',')) == ['-', '-', 'xx', 'zz']
