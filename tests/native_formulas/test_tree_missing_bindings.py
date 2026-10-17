"""GenroPy 5ddb6813dc: missing bindings mean NULL; supplied values win.

PostgreSQL server binding needs a type for a bare parameter tested with IS NULL,
even for explicit None. Only that assertion uses a typed expression on PG;
the offline contracts retain the original SQL without an automatic cast.
"""
from copy import deepcopy

import pytest

from tests.native_formulas.test_tree_terminals_legacy import live_database


@pytest.fixture(scope='module', params=['db_pg', 'db_sqlite'])
def db(request):
    yield from live_database(request.getfixturevalue(request.param))


def nullable(db, name):
    return f'CAST(:{name} AS TEXT)' if db.adapter.dialect == 'postgres' else f':{name}'


@pytest.mark.parametrize('params', [None, {}, {'root_fkey': None}])
def test_missing_binding_is_null(db, params):
    original = deepcopy(params)
    row = db.execute(f'SELECT {nullable(db, "root_fkey")} IS NULL AS missing', params).rows[0]
    assert bool(row[0]) is True
    assert params == original


@pytest.mark.parametrize('value', [0, False, '', 'ROOT'])
def test_explicit_binding_and_environment_are_preserved(db, value):
    params = {'root_fkey': value}
    with db.tempEnv(binding_probe='environment'):
        row = db.execute(
            f'SELECT :root_fkey AS supplied, {nullable(db, "missing")} IS NULL AS missing, '
            ':env_binding_probe AS context', params).rows[0]
    assert row[0] == value
    assert bool(row[1]) is True
    assert row[2] == 'environment'
    assert params == {'root_fkey': value}


@pytest.mark.parametrize('params', [None, {}, {'root_fkey': None}])
def test_missing_binding_in_tree_fetch_and_count(db, params):
    original = deepcopy(params)
    table = db.table('invc.invoice')
    options = dict(excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True, order_by='')
    reference = table.query('$id', **options)
    # The column supplies the SQL type on both backends. NULL matches no row.
    query = table.query('$id', where='$customer_id=:root_fkey', sqlparams=params, **options)
    assert query.compiled.params['root_fkey'] is None
    assert query.fetch() == []
    assert query.count() == 0
    # IS NULL also works with the explicit type required by PostgreSQL.
    all_rows = table.query('$id', where=f'{nullable(db, "root_fkey")} IS NULL',
                           sqlparams=params, **options)
    expected = reference.fetch()
    assert expected
    assert [tuple(row) for row in all_rows.fetch()] == [tuple(row) for row in expected]
    assert all_rows.count() == len(expected)
    assert params == original
