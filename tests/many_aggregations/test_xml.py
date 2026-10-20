"""Compiled PostgreSQL XML compared with the real typed Bag codec."""
from copy import deepcopy
from xml.etree import ElementTree as ET

from genro_bag import Bag
import pytest

from .bag_samples import TYPES, VALUES
from .test_bag_xml_format import DATA, xml_shape
from .test_contracts import execute, query


@pytest.fixture(autouse=True)
def postgres_only(xml_backend, connection):
    # The frozen wire contains UTC; do not depend on the server's session zone.
    previous = connection.execute("SELECT current_setting('TimeZone')").fetchone()[0]
    connection.execute("SELECT set_config('TimeZone', 'UTC', true)")
    try:
        yield
    finally:
        connection.execute("SELECT set_config('TimeZone', %s, true)", (previous,))


@pytest.fixture
def catalog():
    module = pytest.importorskip('gnr.core.gnrclasses', reason='Optional real GenroPy catalog for typed Bag round-trip')
    return module.GnrClassCatalog()


def typed_query(model):
    casts = dict(code='text', empty='text', missing='text', integer='bigint', amount='numeric',
                 real='double precision', active='boolean', inactive='boolean', day='date',
                 clock='time', utc='timestamptz')
    selection = ','.join(f'CAST(:{name} AS {kind}) AS {name}' for name, kind in casts.items())
    return model.table('app.customer').query(
        f'@invoices.aggr(to_xml({selection}) AS invoices)',
        where='$id=:customer', sqlparams=dict(VALUES, customer=3))


def test_compiled_xml_matches_frozen_bag_types_values_and_escaping(model, connection):
    names, rows = execute(connection, typed_query(model))
    assert names == ['invoices']
    expected = ET.fromstring((DATA / 'rows.xml').read_text())
    expected.remove(expected[1])
    assert xml_shape(rows[0][0]) == xml_shape(ET.tostring(expected))
    actual = ET.fromstring(rows[0][0])[0]
    assert {field.tag: field.get('_T') for field in actual} == TYPES


def test_compiled_xml_roundtrip_restores_all_frozen_python_types(model, connection, catalog):
    _, rows = execute(connection, typed_query(model))
    bag = Bag.from_xml(rows[0][0], legacy_mode=True, catalog=catalog)
    assert [node.label for node in bag] == ['r_0']
    for name, expected in VALUES.items():
        actual = bag.get_item('r_0.' + name)
        assert actual == expected and type(actual) is type(expected)


def test_xml_aliases_last_wins_and_actual_expression_type(model, connection, catalog):
    names, rows = execute(connection, query(model,
        '@invoices.aggr(to_xml($id) AS invoices,'
        'to_xml($total AS amount, $qty AS amount, $total * $qty, $id AS CamelCase) AS invoices)'))
    assert names == ['invoices']
    bag = Bag.from_xml(rows[0][0], legacy_mode=True, catalog=catalog)
    # Auto expression alias and case folding come from the ordinary query.
    field_names, values = execute(connection, model.table('app.invoice').query(
        '$total AS amount, $qty AS amount, $total * $qty, $id AS CamelCase',
        where='$customer_id=:customer', customer=1))
    assert [node.label for node in bag] == ['r_0', 'r_1', 'r_2', 'r_3']
    for index, row in enumerate(values):
        actual = bag.get_item(f'r_{index}')
        assert [node.label for node in actual] == field_names
        for name, expected in zip(field_names, row):
            assert actual.get_item(name) == expected
            assert type(actual.get_item(name)) is type(expected)


def test_xml_explicit_star_and_empty_roundtrip(model, connection, catalog):
    names, rows = execute(connection, query(model,
        '@invoices.aggr(to_xml() AS implicit, to_xml(*) AS explicit)'))
    assert names == ['implicit', 'explicit']
    assert xml_shape(rows[0][0]) == xml_shape(rows[0][1])
    expected_names, expected_rows = execute(connection, model.table('app.invoice').query(
        where='$customer_id=:customer', customer=1))
    assert 'double_total' in expected_names and 'adjusted' not in expected_names
    bag = Bag.from_xml(rows[0][0], legacy_mode=True, catalog=catalog)
    for index, expected in enumerate(expected_rows):
        actual = bag.get_item(f'r_{index}')
        assert [node.label for node in actual] == expected_names
        assert [node.value for node in actual] == list(expected)
    _, empty = execute(connection, query(model, '@invoices.aggr(to_xml())', customer=2))
    assert xml_shape(empty[0][0]) == xml_shape((DATA / 'empty.xml').read_text())
    assert len(Bag.from_xml(empty[0][0], legacy_mode=True, catalog=catalog)) == 0


def test_xml_order_binding_scopes_and_reuse(model, connection):
    relations = model.model.relations.to_xml()
    attributes = {name: deepcopy(table.attributes) for name, table in model.model.tables.items()}
    params = {'offset': 99, 'customer': 1}
    q = model.table('app.customer').query(
        '$id+:offset AS outer_value,'
        "@invoices.order_by('$adjusted_again DESC').aggr(to_xml($adjusted AS value) AS local),"
        '@invoices.aggr(to_xml($total+:offset AS value) AS external)',
        where='$id=:customer', sqlparams=params)
    compiled = q.compiled
    names, rows = execute(connection, q)
    assert names == ['outer_value', 'local', 'external']
    assert rows[0][0] == 100
    for xml, expected in zip(rows[0][1:], [(85, 65, 45, 25), (109, 119, 129, 139)]):
        root = ET.fromstring(xml)
        assert [node.tag for node in root] == ['r_0', 'r_1', 'r_2', 'r_3']
        assert [float(node[0].text) for node in root] == list(expected)
    assert compiled.params['offset'] == 99
    assert {5, 7}.issubset(set(compiled.params.values()))
    model.table('app.invoice').query('$adjusted', where='$id=:offset', offset=3).compiled
    assert q.compiled == compiled and params == {'offset': 99, 'customer': 1}
    assert model.model.relations.to_xml() == relations
    assert {name: table.attributes for name, table in model.model.tables.items()} == attributes


def test_xml_shares_order_with_join_and_json(model, connection):
    _, rows = execute(connection, query(model,
        "@invoices.order_by('@vat_id.rate DESC, $id DESC').aggr("
        "join($code, ',', '-') AS codes, to_json($code) AS json_rows, to_xml($code) AS xml_rows)"))
    assert rows[0][0] == '-,zz,-,xx'
    assert rows[0][1] == [{'code': code} for code in ('', 'zz', None, 'xx')]
    root = ET.fromstring(rows[0][2])
    assert [node[0].text or '' for node in root] == ['', 'zz', '', 'xx']
    assert [node[0].get('_T') for node in root] == [None, None, 'NN', None]


@pytest.mark.parametrize('relation', ['large_invoices', 'above_customer'])
def test_virtual_xml_filters_preserve_outer_rows(model, connection, relation):
    names, rows = execute(connection, model.table('app.customer').query(
        f"$id,@{relation}.order_by('$id DESC').aggr(to_xml($id) AS invoices)", order_by='$id DESC'))
    assert names == ['id', 'invoices']
    assert [(id, [int(node[0].text) for node in ET.fromstring(xml)]) for id, xml in rows] == [
        (3, []), (2, []), (1, [4, 3, 2])]


def test_to_one_prefix_then_xml(model, connection):
    _, rows = execute(connection, model.table('app.invoice').query(
        '$id,@customer_id.@invoices.aggr(to_xml($code) AS invoices)', order_by='$id'))
    assert [len(ET.fromstring(xml)) for id, xml in rows] == [4, 4, 4, 4, 1]
    last = ET.fromstring(rows[-1][1])
    assert last[0].tag == 'r_0' and last[0][0].get('_T') == 'NN'
