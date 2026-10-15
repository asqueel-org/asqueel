"""Application queries compile through the real model/dialect/driver without I/O."""
from datetime import date
from decimal import Decimal
import re

import pytest

from asqueel import (
    Column, PostgresCompiler, ResolvedModel, SqlDatabaseConfig, SqlEnvironment,
    Table, UnsupportedFeatureError, build_database,
)
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


@pytest.fixture(params=['postgresql', 'sqlite'])
def database(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Compilation attempted database I/O')

    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    root = config.source.db('compile_only', implementation=request.param)
    pkg = root.packages().package('sales', sqlschema='main', sqlprefix=True)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('sales.customer.id')
    invoice.column('total', dtype='N')
    invoice.column('issued', dtype='D')
    with build_database(config) as db:
        db.currentEnv.update(workdate=date(2026, 10, 14), locale='it')
        yield db


def assert_bindings(compiled):
    pattern = r'%\((\w+)\)s' if compiled.dialect == 'postgresql' else r':(\w+)'
    assert set(re.findall(pattern, compiled.sql)) == set(compiled.params)


def test_sql_and_typed_kwargs_are_complete_without_execution(database):
    value = Decimal('100.50')
    query = database.table('sales.invoice').query(
        columns='$id, @customer_id.name AS customer, COALESCE($total,0) AS total, '
                'CASE WHEN $total >= :threshold THEN :high ELSE :low END AS category',
        where='$issued <= :env_workdate AND $total >= :threshold',
        order_by='@customer_id.name', threshold=value, high='alto', low='basso')
    compiled = query.compiled
    assert_bindings(compiled)
    assert compiled.sql.count('LEFT JOIN') == 1
    assert compiled.params == {'threshold': value, 'high': 'alto', 'low': 'basso',
                               'env_workdate': date(2026, 10, 14)}
    assert isinstance(compiled.params['threshold'], Decimal)
    assert isinstance(compiled.params['env_workdate'], date)
    assert database.outcome == 'not_started'


def test_collection_collision_and_query_reuse_keep_caller_values(database):
    ids = [1, 2]
    query = database.table('invoice').query(
        columns='$id', where='$id IN :ids AND $id <> :ids_0 AND $issued=:env_workdate',
        ids=ids, ids_0=3)
    ids.append(99)
    first = query.compiled
    with database.tempEnv(workdate=date(2026, 10, 15)):
        second = query.compiled
    third = query.compiled
    assert first.sql == second.sql == third.sql
    assert first.params == third.params
    assert second.params['env_workdate'] == date(2026, 10, 15)
    assert first.params['ids_0'] == 3
    assert sorted(v for v in first.params.values() if isinstance(v, int)) == [1, 2, 3]
    for compiled in (first, second, third):
        assert_bindings(compiled)


def test_in_range_uses_legacy_inclusive_null_bound_algorithm(database):
    compiled = database.table('invoice').query(
        columns='$id', where='#IN_RANGE($total, :low, :high)', low=None, high=Decimal('5')).compiled
    assert_bindings(compiled)
    assert '#IN_RANGE' not in compiled.sql
    assert compiled.sql.count('IS NULL') == 4
    assert compiled.sql.count('IS NOT NULL') == 4
    assert compiled.sql.count('<=') == 2
    assert compiled.sql.count('>=') == 2
    assert compiled.params == {'low': None, 'high': Decimal('5')}


@pytest.mark.parametrize('period, dates, operator', [
    ('oggi', [date(2026, 10, 14)], '='),
    ('mese scorso', [date(2026, 9, 1), date(2026, 9, 30)], 'BETWEEN'),
    ('2025', [date(2025, 1, 1), date(2025, 12, 31)], 'BETWEEN'),
    ('2026-01-01;2026-01-31', [date(2026, 1, 1), date(2026, 1, 31)], 'BETWEEN'),
    ('2026-01-01,2026-01-31', [date(2026, 1, 1), date(2026, 1, 31)], 'BETWEEN'),
    ('dal 2026-01-01', [date(2026, 1, 1)], '>='),
    ('al 2026-01-31', [date(2026, 1, 31)], '<='),
    ('sempre', [], 'true'),
    (None, [], 'true'),
])
def test_period_uses_existing_decoder_and_binds_only_dates(database, period, dates, operator):
    compiled = database.table('invoice').query(
        columns='$id', where='#PERIOD($issued, :period)', period=period).compiled
    assert_bindings(compiled)
    assert '#PERIOD' not in compiled.sql
    assert operator in compiled.sql
    assert list(compiled.params.values()) == dates
    assert compiled.input_parameters == ('period',)


def test_period_collision_and_recompilation(database):
    query = database.table('invoice').query(
        columns='$id', where='#PERIOD($issued, period) AND $id=:period_from',
        period='oggi', period_from=41)
    first = query.compiled
    with database.tempEnv(workdate=date(2026, 10, 15)):
        second = query.compiled
    assert first.params['period_from'] == second.params['period_from'] == 41
    assert date(2026, 10, 14) in first.params.values()
    assert date(2026, 10, 15) in second.params.values()
    assert first.sql == second.sql
    assert first.environment.keys == ('locale', 'workdate')
    assert_bindings(first)
    assert_bindings(second)


@pytest.mark.parametrize('macro', ['#ENV(company)', '#PREF(company)', '#TSQUERY($total,:search)',
                                  '#BAG($total)', '#IN_RANGE($total,0,1)', '#PERIOD($issued,period)'])
def test_macro_not_valid_in_direct_projection_is_explicit(database, macro):
    with pytest.raises(UnsupportedFeatureError, match='macro'):
        database.table('invoice').query(columns=macro + ' AS value').compiled


def test_macro_text_inside_literals_comments_and_percent_is_preserved(database):
    compiled = database.table('invoice').query(
        columns="'#PERIOD($issued,missing) 50%' AS literal, $id",
        where='$id=:id /* #IN_RANGE($total,:missing,1) */', id=2).compiled
    assert "'#PERIOD($issued,missing) 50" in compiled.sql
    assert '/* #IN_RANGE($total,:missing,1) */' in compiled.sql
    assert compiled.params == {'id': 2}


def test_missing_macro_parameter_fails_without_execution(database):
    with pytest.raises(ValueError, match='Missing query parameter: period'):
        database.table('invoice').query(columns='$id', where='#PERIOD($issued,period)').compiled


def test_period_repeated_in_where_reuses_bounds_and_keeps_environment(database):
    compiled = database.table('invoice').query(
        columns='$id', where='#PERIOD($issued,period) OR #PERIOD($issued,:period)',
        period='mese scorso').compiled
    assert list(compiled.params.values()) == [date(2026, 9, 1), date(2026, 9, 30)]
    assert compiled.sql.count('BETWEEN') == 2
    assert_bindings(compiled)


def test_formula_in_range_and_subquery_period_use_existing_scopes():
    # Low-level formula route already supported; native formula translation
    # remains the later step of the plan.
    owner = Table('owner', columns={
        'id': Column('id', 'L'),
        'within': Column('within', 'B', formula='#IN_RANGE($id,:low,:high)'),
        'total': Column('total', 'L', select={
            'table': 'item', 'columns': 'COUNT(*)',
            'where': '$owner_id=#THIS.id AND #PERIOD($issued,period)',
            'sqlparams': {'period': 'oggi'},
        }),
    })
    item = Table('item', columns={'owner_id': Column('owner_id', 'L'),
                                 'issued': Column('issued', 'D')})
    env = SqlEnvironment({'workdate': date(2026, 10, 14), 'locale': 'it'})
    compiler = PostgresCompiler(ResolvedModel({t.key: t for t in (owner, item)}),
                                environment=env)
    compiled = compiler.select('owner', '$within, $total',
                                sqlparams={'low': None, 'high': 5, 's1_period_from': 11},
                                where='$id=:s1_period_from')
    assert compiled.params['s1_period_from'] == 11
    assert date(2026, 10, 14) in compiled.params.values()
    assert '#THIS' not in compiled.sql and '#PERIOD' not in compiled.sql
    assert_bindings(compiled)


def test_direct_compiler_period_needs_explicit_workdate_and_locale():
    table = Table('t', columns={'issued': Column('issued', 'D')})
    compiler = PostgresCompiler(ResolvedModel({table.key: table}))
    with pytest.raises(ValueError, match='workdate and locale'):
        compiler.select('t', where='#PERIOD($issued,period)', sqlparams={'period': 'today'})
