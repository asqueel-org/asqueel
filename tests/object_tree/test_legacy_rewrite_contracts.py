"""Independent legacy targets for the rewrite; known missing features stay xfail.

Expected SQL comes only from fa35e5ad, never from the current compiler. Strict
xfails make both unexpected errors and newly completed contracts visible. Remove
each marker when its port is implemented and verified, not by updating the oracle.
"""
from datetime import date
import json
from pathlib import Path
import re

import pytest

from asqueel import AsqueelDb, UnsupportedFeatureError
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from examples.test_invoice_pg import source

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads((ROOT/'tests/oracles/legacy_rewrite_phase1.json').read_text())
READY = {'physical', 'case_coalesce', 'direct', 'two_hops', 'three_hops',
         'reuse_across_clauses', 'alias_and_direct_reuse', 'composite_join',
         'composite_two_paths', 'symbolic_relation_parameter',
         'different_paths_same_table', 'formula_relation', 'formula_dependencies',
         'correlated_subqueries', 'formula_chain', 'formula_parameters',
         'named_subqueries', 'subquery_column', 'group_star', 'star', 'macro_range', 'default_pkey'}
# Explicit scope change: these historical exploding-row requests must not be
# imported. Keep the frozen oracle untouched, and assert rejection separately.
MANY = {'inverse', 'inverse_reuse', 'inverse_forward', 'group_inverse',
        'distinct_inverse', 'implicit_distinct_hidden_order', 'count_inverse_explicit',
        'count_inverse_filter', 'default_inverse'}


def normalized(sql):
    return ' '.join(re.sub(r'\bAS (t\d+(?:_t\d+)*)\b', r'AS "\1"', sql).split())


def local_bindings(sql, params, dialect):
    """Compare local binding identity and values, not process-dependent id()."""
    pattern = r'%\((\w+)\)s' if dialect == 'postgres' else r':(\w+)'
    names = list(dict.fromkeys(re.findall(pattern, sql)))
    assert set(names) == set(params)
    positions = {name: f'LOCAL_{i}' for i, name in enumerate(names)}
    return re.sub(pattern, lambda m: positions[m[1]], sql), [params[name] for name in names]


@pytest.fixture(params=['sqlite', 'postgres'])
def database(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Contract compilation attempted I/O')
    for driver in (PostgresAdapter, SqliteAdapter):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    monkeypatch.setattr(AsqueelDb, 'execute', forbidden)
    config = source()
    config.source.get_node('db').attr['implementation'] = request.param
    db = AsqueelDb(config)
    try:
        db.currentEnv['workdate'] = date(2026, 2, 1)
        yield db
    finally:
        db.closeConnection()


def contract_parameters():
    # Dialect is supplied by the fixture; one request is shared by both oracles.
    for case in ORACLE['cases']:
        if case['dialect'] != 'sqlite':
            continue
        request = case['request']
        name = request['name']
        marks = []
        if name in MANY:
            continue
        if name not in READY:
            marks.append(pytest.mark.xfail(
                strict=True, raises=AttributeError if request['count'] else UnsupportedFeatureError,
                reason='Phase 1 baseline: corresponding legacy branch is not connected to the tree'))
        yield pytest.param(name, id=name, marks=marks)


@pytest.mark.parametrize('name', list(contract_parameters()))
def test_legacy_sql_and_kwargs_contract(database, name):
    case = next(c for c in ORACLE['cases']
                if c['dialect'] == database.adapter.dialect and c['request']['name'] == name)
    request, expected = case['request'], case['expected']
    query = database.table(request['table']).query(
        request['columns'], sqlparams=request['params'], **request['options'])
    if name == 'default_pkey':
        # Agreed new default: pkey is opt-in; the explicit switch reproduces legacy.
        assert [c.name for c in query.compiled.columns] == ['inv_number']
        query = database.table(request['table']).query(
            request['columns'], sqlparams=request['params'], addPkeyColumn=True, **request['options'])
    actual = query._compile(database.compiler.count) if request['count'] else query.compiled
    sql, params = actual.sql, dict(actual.params)
    expected_sql = expected['sql']
    expected_params = {k: v for k, v in expected['params'].items() if k != 'jc_kwargs'}
    if name == 'macro_range':
        # Approved exception: typed comparisons precede NULL checks so psycopg
        # can bind absent bounds. Keep the frozen legacy oracle unchanged.
        low, high = (('%(low)s', '%(high)s') if database.adapter.dialect == 'postgres'
                     else (':low', ':high'))
        approved_where = (
            f'((("t0"."total">={low} AND "t0"."total"<={high} AND {low} IS NOT NULL AND {high} IS NOT NULL) OR '
            f'({low} IS NULL AND {high} IS NOT NULL AND "t0"."total"<={high}) OR '
            f'({low} IS NOT NULL AND {high} IS NULL AND "t0"."total">={low}) OR '
            f'({low} IS NULL AND {high} IS NULL)))')
        before, rest = expected_sql.split('WHERE ', 1)
        _, after = rest.split('\nORDER BY ', 1)
        expected_sql = before + 'WHERE ' + approved_where + '\nORDER BY ' + after
    if name == 'formula_parameters':
        # Local scope ownership is the contract already agreed; names include
        # id() in the legacy and are deliberately not a process-stable API.
        sql, params = local_bindings(sql, params, database.adapter.dialect)
        expected_sql, expected_params = local_bindings(
            expected_sql, expected_params, database.adapter.dialect)
    assert normalized(sql) == normalized(expected_sql)
    assert params == expected_params
    again = query._compile(database.compiler.count) if request['count'] else query.compiled
    assert again.sql == actual.sql
    assert dict(again.params) == dict(actual.params)
    if expected.get('columns'):
        assert [c.name for c in actual.columns] == expected['columns']
    assert database._connections == {}


@pytest.mark.parametrize('name', sorted(MANY))
def test_legacy_exploding_requests_are_deliberately_unsupported(database, name):
    case = next(c for c in ORACLE['cases']
                if c['dialect'] == database.adapter.dialect and c['request']['name'] == name)
    request = case['request']
    # Reject the SELECT itself, including requests formerly consumed by count.
    with pytest.raises(UnsupportedFeatureError):
        database.table(request['table']).query(
            request['columns'], sqlparams=request['params'], **request['options']).compiled
    assert database._connections == {}
