"""Derived virtual relations intersect filters, with independent local bindings."""
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from asqueel import UnsupportedFeatureError, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver

from .conftest import source
from .test_contracts import execute, json_value


@pytest.fixture(scope='module')
def derived_model(backend):
    config = source(backend)
    customer = config.source['db.packages.app.tables.customer']
    customer.formulaColumn('threshold', '$id * :factor', var_factor=15, dtype='N')
    customer.virtualRelation('lower', relation='@invoices',
                             condition='$total>:var_limit', var_limit='$threshold')
    customer.virtualRelation('window', relation='@lower',
                             condition='$total<:var_limit', var_limit='$id * 35')
    customer.virtualRelation('or_base', relation='@invoices', condition='$total=10 OR $total=30')
    customer.virtualRelation('or_derived', relation='@or_base', condition='$qty=1 OR $qty=3')
    customer.virtualRelation('third', relation='@window',
                             condition='@vat_id.rate=:var_limit', var_limit='$id * 20')
    customer.virtualRelation('unchanged', relation='@third')
    customer.virtualRelation('parameter_base', relation='@invoices',
                             condition='$total>:var_limit AND $total<:var_limit2',
                             var_limit='$id * :low', var_limit2='$id * :high')
    customer.virtualRelation('parameter_derived', relation='@parameter_base',
                             condition='$total<:var_limit', var_limit='$id * :upper')
    customer.virtualRelation('ask_base', relation='@invoices', condition='$total>:ask_min',
                             ask={'fields': [{'name': 'min', 'dtype': 'N'}]})
    customer.virtualRelation('ask_derived', relation='@ask_base', condition='$total>0')
    customer.virtualRelation('cycle_a', relation='@cycle_b')
    customer.virtualRelation('cycle_b', relation='@cycle_a')
    customer.virtualRelation('missing', relation='@absent')
    invoice = config.source['db.packages.app.tables.invoice']
    invoice.virtualRelation('customer_window', relation='@customer_id.@window',
                            condition='$total>=:var_limit', var_limit='$total')

    def forbidden(*args, **kwargs):
        pytest.fail('Derived aggregation compilation attempted database I/O')

    with pytest.MonkeyPatch.context() as patch:
        for driver in (PsycopgDriver, SqliteDriver):
            patch.setattr(driver, 'connect', forbidden)
            patch.setattr(driver, 'execute', forbidden)
        with build_database(config) as database:
            yield database
            assert database._connections == {}


@pytest.mark.parametrize('relation, expected', [
    ('window', [(1, 2, 50), (2, 0, None), (3, 0, None)]),
    ('third', [(1, 1, 30), (2, 0, None), (3, 0, None)]),
    ('unchanged', [(1, 1, 30), (2, 0, None), (3, 0, None)]),
    ('or_derived', [(1, 1, 30), (2, 0, None), (3, 0, None)]),
])
def test_filters_intersect_before_aggregation(derived_model, connection, relation, expected):
    q = derived_model.table('app.customer').query(
        f'$id,@{relation}.aggr(count() AS n, sum($total) AS amount)', order_by='$id')
    names, rows = execute(connection, q)
    assert names == ['id', 'n', 'amount']
    assert rows == expected


def test_repeated_uses_keep_bindings_inputs_and_model_isolated(derived_model, connection):
    tables = derived_model.model.tables
    before = {name: deepcopy({key: child.attributes for key, child in table.children.items()})
              for name, table in tables.items()}
    params = {'low': 15, 'high': 50, 'upper': 35, 'var_limit': 99}
    q = derived_model.table('app.customer').query(
        '$id+:var_limit AS external,'
        '@parameter_derived.aggr(sum($total) AS amount),'
        '@parameter_derived.aggr(count() AS n),'
        '@lower.aggr(sum($total) AS lower_amount),'
        '@window.aggr(sum($adjusted) AS adjusted)',
        where='$id=1', sqlparams=params)
    plan = derived_model.compiler.plan_select('app.customer',
        columns='@parameter_derived.aggr(count() AS n)', sqlparams=params)
    # Every declaration uses the existing allocator, even when its SQL expression
    # consumes the temporary name before the final DB-API parameter preparation.
    locals_ = [name for name in plan.local_parameters if '_var_limit' in name]
    assert len(locals_) == 3
    assert len({name.split('_var_')[0] for name in locals_}) == 2
    assert not any(name in plan.params for name in locals_)
    compiled = q.compiled
    names, rows = execute(connection, q)
    assert names == ['external', 'amount', 'n', 'lower_amount', 'adjusted']
    assert rows == [(100, 50, 2, 90, 110)]
    assert set(compiled.input_parameters) == set(params)
    assert compiled.params['var_limit'] == 99
    assert params == {'low': 15, 'high': 50, 'upper': 35, 'var_limit': 99}
    derived_model.table('app.customer').query('@window.aggr(count())').compiled
    assert q.compiled == compiled
    assert {name: {key: child.attributes for key, child in table.children.items()}
            for name, table in tables.items()} == before


@pytest.mark.parametrize('relation, expected', [
    ('@customer_id.@window', [(1, 2), (2, 2), (3, 2), (4, 2), (5, 0)]),
    ('@customer_window', [(1, 2), (2, 2), (3, 1), (4, 0), (5, 0)]),
])
def test_each_level_resolves_vars_on_its_source_row(derived_model, connection, relation, expected):
    q = derived_model.table('app.invoice').query(f'$id,{relation}.aggr(count() AS n)', order_by='$id')
    assert execute(connection, q)[1] == expected


def test_ordered_join_and_json_share_derived_filters(derived_model, connection):
    q = derived_model.table('app.customer').query(
        "$id,@window.order_by('$id DESC').aggr("
        "join($code, ',', '-') AS codes, to_json($id, $adjusted) AS invoices)", order_by='$id')
    names, rows = execute(connection, q)
    assert names == ['id', 'codes', 'invoices']
    assert rows[0][:2] == (1, 'zz,-')
    assert json_value(rows[0][2]) == [{'id': 3, 'adjusted': 65}, {'id': 2, 'adjusted': 45}]
    assert [(row[0], row[1], json_value(row[2])) for row in rows[1:]] == [(2, '', []), (3, '', [])]


def test_xml_uses_derived_filters(derived_model, connection, xml_backend):
    q = derived_model.table('app.customer').query(
        "@window.order_by('$id DESC').aggr(to_xml($id) AS invoices)", where='$id=1')
    root = ET.fromstring(execute(connection, q)[1][0][0])
    assert [row.find('id').text for row in root] == ['3', '2']


@pytest.mark.parametrize('relation', ['ask_base', 'ask_derived'])
def test_ask_remains_unsupported_at_any_level(derived_model, relation):
    with pytest.raises(UnsupportedFeatureError, match='ask'):
        derived_model.table('app.customer').query(f'@{relation}.aggr(count())').compiled


def test_cycles_are_reported_without_unbounded_recursion(derived_model):
    with pytest.raises(ValueError, match='Cyclic virtual relation'):
        derived_model.table('app.customer').query('@cycle_a.aggr(count())').compiled


def test_unknown_base_is_reported(derived_model):
    with pytest.raises(ValueError, match='Unknown relation.*absent'):
        derived_model.table('app.customer').query('@missing.aggr(count())').compiled
