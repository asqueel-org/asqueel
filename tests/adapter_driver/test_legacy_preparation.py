"""Legacy execute/adapter preparation contracts, with all database I/O denied."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest

from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver
from asqueel.drivers.sql import postgres_collections


ORACLE = json.loads((Path(__file__).parents[1] / 'oracles/legacy_r3.json').read_text())


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {'type', 'value'}:
            kind, data = value['type'], value['value']
            if kind in ('tuple', 'set'):
                return {'tuple': tuple, 'set': set}[kind](decode(data))
            return {'bytes': bytes.fromhex, 'date': date.fromisoformat,
                    'datetime': datetime.fromisoformat, 'Decimal': Decimal}[kind](data)
        return {key: decode(item) for key, item in value.items()}
    return value


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('SQL preparation attempted database I/O or a second structured formatting pass')
    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', denied)
        monkeypatch.setattr(driver, 'execute', denied)
        assert not hasattr(driver, 'prepare')


@pytest.mark.parametrize('record', ORACLE['records'], ids=lambda r: ':'.join(
    [r['kind'], r.get('dialect', 'postgresql'), r['name']]))
def test_original_preparation_oracle(record):
    params = decode(record['params'])
    before = deepcopy(params)
    if record['kind'] == 'pg3_collection':
        values = deepcopy(params)
        actual = {'sql': postgres_collections(record['sql'], values), 'params': values}
    else:
        driver = PsycopgDriver() if record['dialect'] == 'postgresql' else SqliteDriver()
        query = driver.prepare_sql(record['sql'], params, decode(record['snapshot']))
        actual = {'sql': query.sql, 'params': dict(query.params)}
    expected = decode(record['legacy']['value'])
    if record['kind'] == 'prepared' and record['name'] == 'missing':
        # Keep the fa35e5ad oracle intact; develop 5ddb6813dc changes this case.
        expected['params']['missing'] = None
    if (record['kind'], record.get('dialect'), record['name']) == ('prepared', 'sqlite', 'literal_operator'):
        # Approved ILIKE fix: literals stay intact; retain the historical oracle.
        expected['sql'] = record['sql']
    assert actual == expected
    assert params == before


@pytest.mark.parametrize('driver', [PsycopgDriver(), SqliteDriver()], ids=['postgresql', 'sqlite'])
def test_common_value_preparation_does_not_modify_inputs(driver):
    args = {'value': b'\\$id', 'escaped': r'\@customer_id.name', 'day': date(2026, 10, 14),
            'amount': Decimal('12.50'), 'absent': None}
    original = deepcopy(args)
    query = driver.prepare_sql('SELECT :value,:escaped,:day,:amount,:absent', args, {})
    assert query.params == dict(original, value='$id', escaped='@customer_id.name')
    assert args == original


@pytest.mark.parametrize('driver', [PsycopgDriver(), SqliteDriver()], ids=['postgresql', 'sqlite'])
def test_environment_defaults_explicit_override_and_snapshot(driver):
    snapshot = {'workdate': date(2026, 10, 14)}
    query = driver.prepare_sql('SELECT :env_workdate,:env_missing', {}, snapshot)
    assert query.params == {'env_workdate': snapshot['workdate'], 'env_missing': None}
    assert query.environment.keys == ('missing', 'workdate')
    assert query.environment.values == snapshot
    explicit = driver.prepare_sql('SELECT :env_workdate', {'env_workdate': None}, snapshot)
    assert explicit.params == {'env_workdate': None}
    assert explicit.environment is None


@pytest.mark.parametrize('driver', [PsycopgDriver(), SqliteDriver()], ids=['postgresql', 'sqlite'])
@pytest.mark.parametrize('params', [None, {}, {'root_fkey': None}])
def test_missing_binding_is_prepared_as_null(driver, params):
    # GenroPy 5ddb6813dc: missing and explicit None have the same value.
    before = deepcopy(params)
    query = driver.prepare_sql('SELECT :root_fkey IS NULL AS missing', params, {})
    placeholder = '%(root_fkey)s' if driver.dialect == 'postgresql' else ':root_fkey'
    assert query.sql == f'SELECT {placeholder} IS NULL AS missing'
    assert query.params == {'root_fkey': None}
    assert query.input_parameters == ('root_fkey',)
    assert params == before


@pytest.mark.parametrize('driver', [PsycopgDriver(), SqliteDriver()], ids=['postgresql', 'sqlite'])
@pytest.mark.parametrize('value', [0, False, '', 'ROOT'])
def test_missing_binding_preserves_explicit_values_and_environment(driver, value):
    params = {'root_fkey': value, 'unused': 9}
    before = deepcopy(params)
    snapshot = {'binding_probe': 'environment'}
    query = driver.prepare_sql(
        'SELECT :root_fkey AS supplied, :missing IS NULL AS missing, '
        ':env_binding_probe AS context', params, snapshot)
    assert query.params == dict(params, missing=None, env_binding_probe='environment')
    assert params == before
    assert snapshot == {'binding_probe': 'environment'}


@pytest.mark.parametrize('driver', [PsycopgDriver(), SqliteDriver()], ids=['postgresql', 'sqlite'])
def test_missing_bindings_respect_escapes_collections_and_environment_override(driver):
    params = {'ids': [1, 2], 'env_binding_probe': None}
    query = driver.prepare_sql(
        r"SELECT '\:literal', CAST(:missing AS INTEGER), :env_binding_probe WHERE 1 IN :ids",
        params, {'binding_probe': 'environment'})
    suffix = '_' if driver.dialect == 'postgresql' else ''
    assert query.params == {'missing': None, 'env_binding_probe': None,
                            f'ids{suffix}0': 1, f'ids{suffix}1': 2}
    assert query.environment is None
    assert params == {'ids': [1, 2], 'env_binding_probe': None}


def test_original_base_adapter_sqltext_shapes():
    # Port of TestSqlDbAdapter.test_sqltext, narrowed to the SQLite base algorithm.
    for values in ([1, 2, 3], (1, 2, 3), {1, 2, 3}, [1]):
        query = SqliteDriver().prepare_sql('SELECT foobar FROM tab WHERE a = :test', {'test': values}, {})
        assert 'test0' in query.sql
        assert query.params['test0'] == 1
        if len(values) > 1:
            assert 'test1' in query.sql and query.params['test1'] == 2
    for value in (1, 'ciao'):
        query = SqliteDriver().prepare_sql('SELECT foobar FROM tab WHERE a = :test', {'test': value}, {})
        assert query.params == {'test': value}
        assert 'test0' not in query.sql


def test_original_double_colon_contracts():
    # Port of the four PostgreSQL TestPrepareSqlTextDoubleColon methods.
    driver = PsycopgDriver()
    sql = driver.prepare_sql('SELECT col::vector FROM t', {}, {}).sql
    assert '::vector' in sql and '%(vector)s' not in sql
    assert '%(id)s' in driver.prepare_sql('WHERE id = :id', {}, {}).sql
    sql = driver.prepare_sql('SELECT (1 - (emb <=> :target::vector)) AS sim WHERE x::text = :val', {}, {}).sql
    assert all(part in sql for part in ('%(target)s', '%(val)s', '::vector', '::text'))
    sql = driver.prepare_sql('WHERE col::text ILIKE :pattern AND num::integer > :threshold', {}, {}).sql
    assert all(part in sql for part in ('%(pattern)s', '%(threshold)s', '::text', '::integer'))


def test_legacy_collection_collisions_are_explicit_not_silently_fixed():
    sqlite = SqliteDriver().prepare_sql('SELECT 1 IN :ids AND 3=:ids0', {'ids': [1, 2], 'ids0': 3}, {})
    pg = PsycopgDriver().prepare_sql('SELECT 1 IN :ids AND 3=:ids_0', {'ids': [1, 2], 'ids_0': 3}, {})
    assert sqlite.params == {'ids0': 1, 'ids1': 2}
    assert pg.params == {'ids_0': 1, 'ids_1': 2}


@pytest.mark.parametrize('other', ['ids2', 'ids_more'])
@pytest.mark.parametrize('reverse', [False, True])
def test_postgres_collection_names_match_whole_parameters(other, reverse):
    pairs = [('ids', [10, 20]), (other, [30, 40])]
    params = dict(reversed(pairs) if reverse else pairs)
    before = deepcopy(params)
    query = PsycopgDriver().prepare_sql(
        f'SELECT id FROM invoice WHERE customer_id IN :ids AND agent_id NOT IN :{other}',
        params, {})
    assert query.sql == (
        'SELECT id FROM invoice WHERE customer_id IN(%(ids_0)s,%(ids_1)s) '
        f'AND agent_id NOT IN(%({other}_0)s,%({other}_1)s)')
    assert query.params == {'ids_0': 10, 'ids_1': 20, other + '_0': 30, other + '_1': 40}
    assert params == before


def test_postgres_repeated_collection_keeps_the_same_bindings():
    query = PsycopgDriver().prepare_sql(
        'SELECT id FROM invoice WHERE customer_id IN :ids OR agent_id in :ids',
        {'ids': [10, 20]}, {})
    assert query.sql == (
        'SELECT id FROM invoice WHERE customer_id IN(%(ids_0)s,%(ids_1)s) '
        'OR agent_id in(%(ids_0)s,%(ids_1)s)')
    assert query.params == {'ids_0': 10, 'ids_1': 20}
