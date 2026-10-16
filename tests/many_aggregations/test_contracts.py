"""Approved aggregate contracts, executed as SQL on each supported dialect.

The XML capability boundary remains explicit on SQLite. SQL is executed directly
by DB-API; no Python aggregation or fetch hook can make these contracts pass.
"""
import json
from xml.etree import ElementTree as ET

import pytest

from asqueel import UnsupportedFeatureError


def execute(connection, query):
    compiled = query.compiled
    assert query.compiled == compiled
    cursor = connection.cursor()
    cursor.execute(compiled.sql, dict(compiled.params))
    names = [column[0] for column in cursor.description]
    return names, cursor.fetchall()


def query(model, expression, customer=1, **options):
    return model.table('app.customer').query(
        expression, where='$id=:customer', sqlparams={'customer': customer}, **options)


VALUE_CASES = [
    ('count()', ['_invoices_count'], [4]),
    ('count() AS n', ['n'], [4]),
    ('sum($total), avg($total), min($total), max($total)',
     ['_invoices_total_sum', '_invoices_total_avg', '_invoices_total_min', '_invoices_total_max'], [100, 25, 10, 40]),
    ('sum($total AS amount, $qty AS quantity)', ['amount', 'quantity'], [100, 7]),
    ('sum($total, $qty)', ['_invoices_total_sum', '_invoices_qty_sum'], [100, 7]),
    ('avg($total, $qty)', ['_invoices_total_avg', '_invoices_qty_avg'], [25, 1.75]),
    ('min($total, $qty)', ['_invoices_total_min', '_invoices_qty_min'], [10, 1]),
    ('max($total, $qty)', ['_invoices_total_max', '_invoices_qty_max'], [40, 3]),
    ('avg($total AS amount, $qty AS quantity)', ['amount', 'quantity'], [25, 1.75]),
    ('min($total AS amount, $qty AS quantity)', ['amount', 'quantity'], [10, 1]),
    ('max($total AS amount, $qty AS quantity)', ['amount', 'quantity'], [40, 3]),
    ('sum($total * $qty) AS amount', ['amount'], [150]),
    ('sum(CASE WHEN $qty>1 THEN $total ELSE 0 END) AS amount', ['amount'], [30]),
    ('sum($double_total) AS doubled', ['doubled'], [200]),
    ('sum($adjusted) AS adjusted', ['adjusted'], [220]),
    ('sum(@vat_id.rate) AS taxes', ['taxes'], [60]),
    ('sum($tax_rate) AS taxes', ['taxes'], [60]),
    ('min(total), avg(qty)', ['_invoices_total_min', '_invoices_qty_avg'], [10, 1.75]),
    ("join($code, ',')", ['_invoices_code_join'], ['xx,,zz,']),
    ("join($code, ',', '-empty-') AS codes", ['codes'], ['xx,-empty-,zz,-empty-']),
    ("join($code, ',', 'null') AS codes", ['codes'], ['xx,null,zz,null']),
    ("join($code, ',', '') AS codes", ['codes'], ['xx,,zz,']),
    ("join($code, ';', '-empty-')", ['_invoices_code_join'], ['xx;-empty-;zz;-empty-']),
    ('count() AS result, sum($total) AS result', ['result'], [100]),
    ("join($code, ','), join($code, ';')", ['_invoices_code_join'], ['xx;;zz;']),
    ('sum($total) AS amount, avg($qty)', ['amount', '_invoices_qty_avg'], [100, 1.75]),
]


@pytest.mark.parametrize('expression, names, expected', VALUE_CASES)
def test_approved_values_and_aliases(model, connection, expression, names, expected):
    actual_names, rows = execute(connection, query(model, f'@invoices.aggr({expression})'))
    assert actual_names == names
    assert [list(row) for row in rows] == [expected]


@pytest.mark.parametrize('aggregate, expected', [
    ('count()', 0), ('sum($total)', None), ('avg($total)', None),
    ('min($total)', None), ('max($total)', None),
    ("join($code, ',', '-empty-')", ''),
])
def test_no_correlated_rows(model, connection, aggregate, expected):
    names, rows = execute(connection, query(model, f'@invoices.aggr({aggregate} AS result)', customer=2))
    assert names == ['result']
    assert rows == [(expected,)]


def test_null_code_in_existing_row_is_not_an_empty_set(model, connection):
    names, rows = execute(connection, query(
        model, "@invoices.aggr(count() AS n, join($code, ',', '-empty-') AS codes)", customer=3))
    assert names == ['n', 'codes']
    assert rows == [(1, '-empty-')]


def test_many_rows_never_multiply_outer_rows(model, connection):
    names, rows = execute(connection, model.table('app.customer').query(
        '$id,@invoices.aggr(count() AS n, sum($total) AS total)', order_by='$id DESC'))
    assert names == ['id', 'n', 'total']
    assert rows == [(3, 1, 7), (2, 0, None), (1, 4, 100)]


def test_order_override_applies_to_join(model, connection):
    names, rows = execute(connection, query(model,
        "@invoices.order_by('$id DESC').aggr(join($code, ',', '-') AS codes)"))
    assert names == ['codes']
    assert rows == [('-,zz,-,xx',)]


def test_two_calls_keep_local_order_and_bindings(model, connection):
    q = model.table('app.customer').query(
        "$id + :offset AS outer_value,"
        "@invoices.aggr(sum($adjusted) AS amount, join($code, ',') AS ascending),"
        "@invoices.order_by('$id DESC').aggr(join($code, ',') AS descending)",
        where='$id=:customer', sqlparams={'offset': 99, 'customer': 1})
    names, rows = execute(connection, q)
    assert names == ['outer_value', 'amount', 'ascending', 'descending']
    assert rows == [(100, 220, 'xx,,zz,', ',zz,,xx')]
    before = q.compiled
    model.table('app.invoice').query('$adjusted', where='$id=:offset', offset=3).compiled
    assert q.compiled == before


def json_value(value):
    return json.loads(value) if isinstance(value, str) else value


@pytest.mark.parametrize('order, expected_ids', [('', [1, 2, 3, 4]), (".order_by('$id DESC')", [4, 3, 2, 1])])
def test_json_selected_columns_alias_formula_relation_and_order(model, connection, order, expected_ids):
    names, rows = execute(connection, query(model,
        f'@invoices{order}.aggr(to_json($id AS number, $double_total, @vat_id.rate AS rate) AS invoices)'))
    assert names == ['invoices']
    assert json_value(rows[0][0]) == [
        {'number': id, 'double_total': id * 20, 'rate': 10 if id < 3 else 20}
        for id in expected_ids]


def test_json_star_is_query_star_including_static_columns(model, connection):
    names, rows = execute(connection, model.table('app.invoice').query(
        where='$customer_id=:customer', customer=1))
    expected = [dict(zip(names, row)) for row in rows]
    assert 'double_total' in names and 'adjusted' not in names
    actual_names, actual = execute(connection, query(model, '@invoices.aggr(to_json())'))
    assert actual_names == ['_invoices_json']
    assert json_value(actual[0][0]) == expected


def test_json_without_rows_is_empty_array(model, connection):
    names, rows = execute(connection, query(model, '@invoices.aggr(to_json())', customer=2))
    assert names == ['_invoices_json']
    assert json_value(rows[0][0]) == []


@pytest.mark.parametrize('order, codes', [('', ['xx', None, 'zz', '']),
                                         (".order_by('$id DESC')", ['', 'zz', None, 'xx'])])
def test_xml_labels_follow_order_without_selecting_primary_key(model, connection, xml_backend, order, codes):
    names, rows = execute(connection, query(model,
        f'@invoices{order}.aggr(to_xml($code) AS invoices)'))
    assert names == ['invoices']
    root = ET.fromstring(rows[0][0])
    assert root.tag == 'GenRoBag'
    assert [node.tag for node in root] == ['r_0', 'r_1', 'r_2', 'r_3']
    for node, expected in zip(root, codes):
        assert [field.tag for field in node] == ['code']
        field = node[0]
        assert (field.get('_T') == 'NN') == (expected is None)
        assert (field.text or '') == (expected or '')


def test_xml_star_and_empty_bag(model, connection, xml_backend):
    star_names, _ = execute(connection, model.table('app.invoice').query())
    names, rows = execute(connection, query(model, '@invoices.aggr(to_xml())'))
    assert names == ['_invoices_xml']
    root = ET.fromstring(rows[0][0])
    assert root.tag == 'GenRoBag' and len(root) == 4
    assert [field.tag for field in root[0]] == star_names
    _, empty = execute(connection, query(model, '@invoices.aggr(to_xml())', customer=2))
    root = ET.fromstring(empty[0][0])
    assert root.tag == 'GenRoBag' and len(root) == 0


def test_sqlite_xml_rejection_identifies_the_missing_capability(model, backend):
    if backend != 'sqlite':
        pytest.skip('SQLite-only capability boundary')
    with pytest.raises(UnsupportedFeatureError) as caught:
        query(model, '@invoices.aggr(to_xml())').compiled
    assert 'to_xml' in str(caught.value) or 'XML' in str(caught.value)


def test_fixture_uses_real_formula_alias_relation_and_static_star(model, connection):
    names, rows = execute(connection, model.table('app.invoice').query(
        '$id,$adjusted,$tax_rate', order_by='$id'))
    assert names == ['id', 'adjusted', 'tax_rate']
    assert rows == [(1, 25, 10), (2, 45, 10), (3, 65, 20), (4, 85, 20), (5, 19, 10)]
    names, _ = execute(connection, model.table('app.invoice').query())
    assert 'double_total' in names and 'adjusted' not in names


@pytest.mark.parametrize('expression', ['@invoices', '@invoices.total'])
def test_bare_many_paths_remain_rejected(model, expression):
    with pytest.raises((UnsupportedFeatureError, ValueError)):
        query(model, expression).compiled


def test_shared_order_for_join_and_json_with_unselected_sort_field(model, connection):
    names, rows = execute(connection, query(model,
        "@invoices.order_by('$qty DESC, $id').aggr("
        "join($code, ',', '-') AS codes, to_json($code) AS invoices)"))
    assert names == ['codes', 'invoices']
    assert rows[0][0] == '-,xx,zz,-'
    assert json_value(rows[0][1]) == [dict(code=value) for value in [None, 'xx', 'zz', '']]


def test_to_one_prefix_changes_aggregation_context(model, connection):
    names, rows = execute(connection, model.table('app.invoice').query(
        '$id,@customer_id.@invoices.aggr(count() AS n, sum($total) AS amount)', order_by='$id'))
    assert names == ['id', 'n', 'amount']
    assert rows == [(1, 4, 100), (2, 4, 100), (3, 4, 100), (4, 4, 100), (5, 1, 7)]


@pytest.mark.parametrize('relation', ['large_invoices', 'above_customer'])
def test_filtered_virtual_many_relations_use_same_aggregation_contract(model, connection, relation):
    names, rows = execute(connection, model.table('app.customer').query(
        f'$id,@{relation}.aggr(count() AS n, sum($total) AS amount)', order_by='$id'))
    assert names == ['id', 'n', 'amount']
    assert rows == [(1, 3, 90), (2, 0, None), (3, 0, None)]


def test_xml_selected_formulas_and_related_fields_preserve_types(model, connection, xml_backend):
    names, rows = execute(connection, query(model,
        '@invoices.aggr(to_xml($qty, $double_total, @vat_id.rate AS rate) AS invoices)'))
    assert names == ['invoices']
    root = ET.fromstring(rows[0][0])
    assert root.tag == 'GenRoBag' and len(root) == 4
    for node, qty, total, rate in zip(root, [2, 3, 1, 1], [20, 40, 60, 80], [10, 10, 20, 20]):
        assert [field.tag for field in node] == ['qty', 'double_total', 'rate']
        for field, dtype, expected in zip(node, ['L', 'N', 'N'], [qty, total, rate]):
            assert field.get('_T') == dtype
            assert float(field.text) == expected


def test_numeric_scopes_reuse_and_model_are_isolated(model, connection):
    from copy import deepcopy
    relations = model.model.relations.to_xml()
    attributes = {name: deepcopy(table.attributes) for name, table in model.model.tables.items()}
    bindings = {'offset': 99, 'customer': 1}
    q = model.table('app.customer').query(
        '$id+:offset AS outer_value,'
        '@invoices.aggr(sum($adjusted) AS adjusted),'
        '@invoices.aggr(sum($total+:offset) AS external, avg($adjusted_again) AS mean)',
        where='$id=:customer', sqlparams=bindings)
    compiled = q.compiled
    names, rows = execute(connection, q)
    assert names == ['outer_value', 'adjusted', 'external', 'mean']
    assert rows == [(100, 220, 496, 57)]
    assert compiled.params['offset'] == 99
    assert set(compiled.input_parameters) == {'offset', 'customer'}
    local_values = {key: value for key, value in compiled.params.items() if key not in bindings}
    assert sorted(local_values.values()) == [5, 7]
    model.table('app.invoice').query('$adjusted', where='$id=:offset', offset=3).compiled
    assert q.compiled == compiled
    assert bindings == {'offset': 99, 'customer': 1}
    assert model.model.relations.to_xml() == relations
    assert {name: table.attributes for name, table in model.model.tables.items()} == attributes


@pytest.mark.parametrize('columns, options', [
    ('$id', {'where': '@invoices.aggr(count())>0'}),
    ('COALESCE(@invoices.aggr(sum($total)),0)', {}),
    ('@invoices.aggr(sum($total,$qty) AS one_name)', {}),
])
def test_no_implicit_scalar_or_tuple_extensions(model, columns, options):
    with pytest.raises((UnsupportedFeatureError, ValueError)):
        model.table('app.customer').query(columns, **options).compiled
