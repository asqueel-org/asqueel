"""JSON collections reuse query projections and correlated SELECT scopes."""
import pytest

from asqueel import build_database
from .conftest import source
from .test_contracts import execute, json_value, query


@pytest.mark.parametrize('selection, expected', [
    ('$total * $qty AS line_total', [{'line_total': n} for n in (20, 60, 30, 40)]),
    ('$code', [{'code': value} for value in ('xx', None, 'zz', '')]),
    ('$id AS value, $qty AS value', [{'value': n} for n in (2, 3, 1, 1)]),
    ('$tax_rate AS rate', [{'rate': n} for n in (10, 10, 20, 20)]),
])
def test_json_projection_expressions_nulls_aliases(model, connection, selection, expected):
    names, rows = execute(connection, query(model, f'@invoices.aggr(to_json({selection}) AS invoices)'))
    assert names == ['invoices']
    assert json_value(rows[0][0]) == expected


def test_outer_alias_collision_keeps_last_json_projection(model, connection):
    names, rows = execute(connection, query(model,
        '@invoices.aggr(to_json($id) AS invoices, to_json($code) AS invoices)'))
    assert names == ['invoices']
    assert json_value(rows[0][0]) == [{'code': value} for value in ('xx', None, 'zz', '')]


def test_explicit_star_uses_the_same_query_expansion(model, connection):
    names, rows = execute(connection, query(model,
        '@invoices.aggr(to_json() AS implicit, to_json(*) AS explicit)'))
    assert names == ['implicit', 'explicit']
    assert json_value(rows[0][0]) == json_value(rows[0][1])
    assert 'double_total' in json_value(rows[0][0])[0]


def test_json_parameters_are_values_and_encoded_in_sql(model, connection):
    note = 'Una "nota"\ncon accento: città e backslash \\'
    q = model.table('app.customer').query(
        '@invoices.aggr(to_json($id, :note AS note, :amount AS amount) AS invoices)',
        where='$id=:customer', sqlparams={'customer': 1, 'note': note, 'amount': 1.25})
    names, rows = execute(connection, q)
    assert names == ['invoices']
    assert json_value(rows[0][0]) == [dict(id=id, note=note, amount=1.25) for id in (1, 2, 3, 4)]
    assert note not in q.compiled.sql


def test_json_order_formulas_and_bindings_stay_local(model, connection):
    from copy import deepcopy
    before_relations = model.model.relations.to_xml()
    before_attributes = {name: deepcopy(table.attributes) for name, table in model.model.tables.items()}
    params = {'customer': 1, 'offset': 99}
    q = model.table('app.customer').query(
        '$id+:offset AS outer_value,'
        "@invoices.order_by('$adjusted_again DESC').aggr(to_json($adjusted AS value) AS local),"
        '@invoices.aggr(to_json($total+:offset AS value) AS external)',
        where='$id=:customer', sqlparams=params)
    compiled = q.compiled
    names, rows = execute(connection, q)
    assert names == ['outer_value', 'local', 'external']
    assert rows[0][0] == 100
    assert json_value(rows[0][1]) == [{'value': n} for n in (85, 65, 45, 25)]
    assert json_value(rows[0][2]) == [{'value': n} for n in (109, 119, 129, 139)]
    assert compiled.params['offset'] == 99
    assert {5, 7}.issubset(set(compiled.params.values()))
    model.table('app.invoice').query('$adjusted', where='$id=:offset', offset=3).compiled
    assert q.compiled == compiled
    assert params == {'customer': 1, 'offset': 99}
    assert model.model.relations.to_xml() == before_relations
    assert {name: table.attributes for name, table in model.model.tables.items()} == before_attributes


@pytest.mark.parametrize('relation', ['large_invoices', 'above_customer'])
def test_virtual_json_filter_order_and_outer_cardinality(model, connection, relation):
    names, rows = execute(connection, model.table('app.customer').query(
        f"$id,@{relation}.order_by('$id DESC').aggr(to_json($id) AS invoices)", order_by='$id DESC'))
    assert names == ['id', 'invoices']
    assert [(id, json_value(value)) for id, value in rows] == [
        (3, []), (2, []), (1, [{'id': 4}, {'id': 3}, {'id': 2}])]


def test_to_one_prefix_then_json(model, connection):
    names, rows = execute(connection, model.table('app.invoice').query(
        '$id,@customer_id.@invoices.aggr(to_json($code) AS invoices)', order_by='$id'))
    assert names == ['id', 'invoices']
    expected = [{'code': value} for value in ('xx', None, 'zz', '')]
    assert [(id, json_value(value)) for id, value in rows] == [
        (1, expected), (2, expected), (3, expected), (4, expected), (5, [{'code': None}])]


def test_json_without_base_order_does_not_add_a_fallback(backend, connection):
    with build_database(source(backend, order_by=None)) as model:
        q = query(model, '@invoices.aggr(to_json($id) AS invoices)')
        assert 'ORDER BY' not in q.compiled.sql
        names, rows = execute(connection, q)
    assert names == ['invoices']
    assert sorted(row['id'] for row in json_value(rows[0][0])) == [1, 2, 3, 4]


@pytest.mark.parametrize('selection', ['$id AS CamelCase,$total', 'CAST($total AS NUMERIC)'])
def test_json_keys_follow_existing_authored_query_names(model, connection, selection):
    # These projection forms already belong to the legacy regression corpus.
    names, rows = execute(connection, model.table('app.invoice').query(
        selection, where='$customer_id=:customer', customer=1))
    _, collected = execute(connection, query(model, f'@invoices.aggr(to_json({selection}) AS invoices)'))
    expected = [dict(zip(names, row)) for row in rows]
    assert json_value(collected[0][0]) == expected
