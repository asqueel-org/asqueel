"""Direct table virtual relations use their authored condition as correlation."""
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from asqueel import UnsupportedFeatureError, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver

from .conftest import source
from .test_contracts import execute, json_value


def direct_source(backend):
    config = source(backend)
    customer = config.source['db.packages.app.tables.customer']
    customer.virtualRelation('direct', table='app.invoice',
                             condition='$customer_id=:var_customer', var_customer='$id')
    customer.formulaColumn('threshold', '$id * :factor', var_factor=15, dtype='N')
    customer.virtualRelation('direct_lower', table='app.invoice',
                             condition='$customer_id=:var_customer AND $total>:var_limit',
                             var_customer='$id', var_limit='$threshold')
    customer.virtualRelation('direct_window', relation='@direct_lower',
                             condition='$total<:var_limit', var_limit='$id * :upper')
    customer.virtualRelation('direct_third', relation='@direct_window', condition='@vat_id.rate=20')
    customer.virtualRelation('price_window', table='app.invoice',
                             condition='$total>:var_limit AND $total<:var_upper',
                             var_limit='$id * 15', var_upper='$id * 35')
    customer.virtualRelation('direct_or', table='app.invoice',
                             condition='$customer_id=:var_customer AND ($total=10 OR $total=30)',
                             var_customer='$id')
    customer.virtualRelation('direct_or_derived', relation='@direct_or', condition='$qty=1 OR $qty=3')
    customer.virtualRelation('direct_ask', table='app.invoice',
                             condition='$customer_id=:var_customer AND $total>:ask_min',
                             var_customer='$id', ask={'fields': [{'name': 'min', 'dtype': 'N'}]})
    customer.virtualRelation('direct_ask_derived', relation='@direct_ask', condition='$total>0')
    return config


@pytest.fixture(scope='module')
def direct_model(backend):
    def forbidden(*args, **kwargs):
        pytest.fail('Direct virtual relation compilation attempted database I/O')

    with pytest.MonkeyPatch.context() as patch:
        for driver in (PsycopgDriver, SqliteDriver):
            patch.setattr(driver, 'connect', forbidden)
            patch.setattr(driver, 'execute', forbidden)
        with build_database(direct_source(backend)) as database:
            yield database
            assert database._connections == {}


@pytest.mark.parametrize('aggregate', [
    'count()', 'sum($total)', 'avg($total)', 'min($total)', 'max($total)',
    'sum($total AS amount, $qty AS quantity)', 'sum($adjusted)', 'sum(@vat_id.rate)',
    "join($code, ',', '-')",
])
def test_direct_and_ordinary_relations_have_same_results(direct_model, connection, aggregate):
    table = direct_model.table('app.customer')
    direct = table.query(f'$id,@direct.aggr({aggregate})', order_by='$id')
    ordinary = table.query(f'$id,@invoices.aggr({aggregate})', order_by='$id')
    assert execute(connection, direct)[1] == execute(connection, ordinary)[1]


def test_no_declared_relation_or_fk_is_needed(backend, connection):
    config = direct_source(backend)
    config.source.get_node('db.packages.app.tables.invoice.columns.customer_id').value.pop_node('relation_0')
    with build_database(config) as db:
        assert db.model.table('app.customer').relations.get_node('@invoices') is None
        q = db.table('app.customer').query('$id,@direct.aggr(count() AS n, sum($total) AS amount)', order_by='$id')
        assert execute(connection, q)[1] == [(1, 4, 100), (2, 0, None), (3, 1, 7)]


def test_authored_condition_is_the_entire_correlation(direct_model, connection):
    # Customer 2 has no invoices, but its numeric window contains invoice 4.
    # There must be no automatic customer_id=id condition added to table=.
    q = direct_model.table('app.customer').query(
        '$id,@price_window.aggr(count() AS n, sum($total) AS amount)', order_by='$id')
    assert execute(connection, q)[1] == [(1, 2, 50), (2, 1, 40), (3, 0, None)]


def test_derived_direct_filters_keep_local_vars_and_inputs(direct_model, connection):
    table = direct_model.table('app.customer')
    before = {key: deepcopy(node.attributes) for key, node in table.model.children.items()}
    params = {'upper': 35, 'var_limit': 99}
    q = table.query('$id+:var_limit AS external,'
                    '@direct_window.aggr(count() AS n, sum($adjusted) AS amount),'
                    '@direct_third.aggr(sum($total) AS last_amount),'
                    '@direct_window.aggr(sum($total) AS repeated)',
                    where='$id=1', sqlparams=params)
    compiled = q.compiled
    assert execute(connection, q)[1] == [(100, 2, 110, 30, 50)]
    assert set(compiled.input_parameters) == set(params)
    assert compiled.params['var_limit'] == 99
    assert params == {'upper': 35, 'var_limit': 99}
    table.query('@direct_window.aggr(count())', upper=25).compiled
    assert q.compiled == compiled
    assert {key: node.attributes for key, node in table.model.children.items()} == before


def test_direct_derivation_parenthesizes_or_conditions(direct_model, connection):
    q = direct_model.table('app.customer').query(
        '$id,@direct_or_derived.aggr(sum($total) AS amount)', order_by='$id')
    assert execute(connection, q)[1] == [(1, 30), (2, None), (3, None)]


def test_to_one_prefix_preserves_direct_source_context(direct_model, connection):
    q = direct_model.table('app.invoice').query(
        '$id,@customer_id.@direct_window.aggr(sum($total) AS amount)', order_by='$id', upper=35)
    assert execute(connection, q)[1] == [(1, 50), (2, 50), (3, 50), (4, 50), (5, None)]


@pytest.mark.parametrize('ordering, expected_ids, expected_codes', [
    ('', [1, 2, 3, 4], 'xx,-,zz,-'),
    (".order_by('$id DESC')", [4, 3, 2, 1], '-,zz,-,xx'),
])
def test_direct_join_and_json_keep_order_and_empty_set(direct_model, connection, ordering, expected_ids, expected_codes):
    q = direct_model.table('app.customer').query(
        f"$id,@direct{ordering}.aggr(join($code, ',', '-') AS codes, "
        'to_json($id, $adjusted, @vat_id.rate AS rate) AS invoices)', order_by='$id')
    rows = execute(connection, q)[1]
    assert rows[0][1] == expected_codes
    data = json_value(rows[0][2])
    assert [item['id'] for item in data] == expected_ids
    assert [item['adjusted'] for item in data] == [i * 20 + 5 for i in expected_ids]
    assert [item['rate'] for item in data] == [10 if i < 3 else 20 for i in expected_ids]
    assert rows[1][:2] == (2, '')
    assert json_value(rows[1][2]) == []


def test_direct_xml_order_and_empty_bag(direct_model, connection, xml_backend):
    q = direct_model.table('app.customer').query(
        "$id,@direct.order_by('$id DESC').aggr(to_xml($id, $adjusted) AS invoices)", order_by='$id')
    rows = execute(connection, q)[1]
    root = ET.fromstring(rows[0][1])
    assert [row.find('id').text for row in root] == ['4', '3', '2', '1']
    assert [row.find('adjusted').text for row in root] == ['85', '65', '45', '25']
    assert ET.fromstring(rows[1][1]).tag == 'GenRoBag'
    assert len(ET.fromstring(rows[1][1])) == 0


@pytest.mark.parametrize('name', ['direct_ask', 'direct_ask_derived'])
def test_direct_ask_is_still_rejected(direct_model, name):
    with pytest.raises(UnsupportedFeatureError, match='ask'):
        direct_model.table('app.customer').query(f'@{name}.aggr(count())').compiled
