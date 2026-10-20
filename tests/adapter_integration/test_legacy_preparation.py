"""Execute the prepared R3 SQL on temporary SQLite and read-only PostgreSQL cases."""
from datetime import date
from decimal import Decimal

import pytest
from genro_toolbox import NamedList

from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter


@pytest.fixture(params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
def database(request, pg_params):
    if request.param == 'sqlite':
        driver = SqliteAdapter(None)
        connection = driver.connect(':memory:')
    else:
        driver = PostgresAdapter(None)
        connection = driver.connect('', dbname='postgres', **pg_params)
    try:
        yield driver, connection
    finally:
        driver.rollback(connection)
        driver.close(connection)


def run(database, sql, args=None):
    """The rows of ``sql`` executed on the adapter's driver cursor, read by name."""
    driver, connection = database
    cursor = driver.execute(connection, driver.prepare_sql(sql, args or {}, {}))
    index = {column[0]: position for position, column in enumerate(cursor.description)}
    return [NamedList(index, row) for row in cursor.fetchall()]


@pytest.mark.parametrize('values,negated,expected', [
    ([1, 2], False, [True, True, None]),
    ([1, None], False, [True, None, None]),
    ([1, 2], True, [False, False, None]),
    ([], False, [False, False, False]),
    ([], True, [True, True, True]),
])
def test_legacy_in_not_in_null_and_empty(database, values, negated, expected):
    op = 'NOT IN' if negated else 'IN'
    result = run(database, 'WITH t0(id) AS (VALUES (1),(2),(NULL)) '
                 f'SELECT "t0"."id" {op} :ids AS matched FROM t0 ORDER BY id NULLS LAST', {'ids': values})
    assert [row['matched'] for row in result] == expected
    assert all(row.keys() == ['matched'] for row in result)


def test_collection_parameter_prefixes_keep_distinct_values(database):
    result = run(database,
        'WITH invoice(id, customer_id, agent_id) AS '
        '(VALUES (1,10,30),(2,10,99),(3,20,40),(4,30,10)) '
        'SELECT id FROM invoice WHERE customer_id IN :ids AND agent_id IN :ids2 ORDER BY id',
        {'ids': [10, 20], 'ids2': [30, 40]})
    assert [row['id'] for row in result] == [1, 3]


def test_unicode_values_escapes_and_types(database):
    result = run(database, "SELECT :soglia_è AS amount, :value AS value, :day AS day, :nothing AS nullable", {
        'soglia_è': Decimal('12.50'), 'value': b'\\$id', 'day': date(2026, 10, 14), 'nothing': None})
    row = result[0]
    driver, _ = database
    # SQLite's existing Decimal adapter binds text; PostgreSQL returns numeric.
    assert row['amount'] == ('12.50' if driver.dialect == 'sqlite' else Decimal('12.50'))
    assert row['value'] == '$id'
    assert str(row['day']) == '2026-10-14'
    assert row['nullable'] is None
    assert run(database, r"SELECT '\:value' AS value")[0]['value'] == ':value'


def test_legacy_operators(database):
    driver, _ = database
    sql = "WITH t0(value) AS (VALUES ('Alice'),('bob')) SELECT value FROM t0 WHERE value ILIKE :pattern"
    assert [r['value'] for r in run(database, sql, {'pattern': 'a%'})] == ['Alice']
    op = 'REGEXP' if driver.dialect == 'postgres' else '~*'
    sql = f"WITH t0(value) AS (VALUES ('Alice'),('bob')) SELECT value FROM t0 WHERE value {op} :pattern"
    assert [r['value'] for r in run(database, sql, {'pattern': '^A'})] == ['Alice']


def test_sqlite_boolean_adapter(database):
    driver, _ = database
    # Actual boolean inputs on PG, integer booleans on SQLite, as in their types.
    values = '(TRUE),(FALSE),(NULL)'
    sql = f'WITH t0(flag) AS (VALUES {values}) SELECT t0.flag IS NOT TRUE AS value FROM t0'
    assert sorted(r['value'] for r in run(database, sql)) == [False, True, True]


def test_driver_percent_protocol(database):
    driver, _ = database
    sql = "SELECT '10%%' AS value, 8 %% 3 AS remainder" if driver.dialect == 'postgres' else "SELECT '10%' AS value, 8 % 3 AS remainder"
    row = run(database, sql)[0]
    assert dict(row) == {'value': '10%', 'remainder': 2}
    if driver.dialect == 'postgres':
        assert run(database, 'SELECT :value::numeric AS value', {'value': 2})[0]['value'] == 2
