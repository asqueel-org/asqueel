"""Real MySQL checks of the execution layer, without a model."""
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest

from asqueel.contracts import CompiledQuery, ResultColumn, UnsupportedFeatureError
from tests.unit_of_work import completed, empty_database

pytestmark = pytest.mark.mysql


@pytest.fixture
def db(mysql_server):
    params, _ = mysql_server
    database = empty_database(implementation='mysql', connect_kwargs=params)
    try:
        yield database.session()
    finally:
        database.close()


def test_session_sql_mode(db):
    (mode,), = db.execute('SELECT @@sql_mode').fetchall()
    assert {'ANSI_QUOTES', 'PIPES_AS_CONCAT', 'NO_BACKSLASH_ESCAPES'} <= set(mode.split(','))


def test_crud_and_rollback(db):
    table = 'v1_runtime_' + uuid4().hex
    db.execute(f'CREATE TABLE "{table}" (id int PRIMARY KEY, value text)')
    result = db.execute(f'INSERT INTO "{table}" VALUES (:id, :value)', {'id': 1, 'value': "l'apostrofo \\ 100%"})
    assert result.rowcount == 1
    db.commit()
    with pytest.raises(RuntimeError):
        with completed(db) as tx:
            tx.execute(f'UPDATE "{table}" SET value = :v', {'v': 'rollback'})
            raise RuntimeError('abort')
    assert [dict(row) for row in db.execute(f'SELECT value FROM "{table}" WHERE value LIKE \'%100%\'').fetchall()] == [
        {'value': "l'apostrofo \\ 100%"}]
    with pytest.raises(UnsupportedFeatureError, match='RETURNING'):
        db.execute(f'DELETE FROM "{table}" RETURNING id')
    db.rollback()


def test_percent_outside_bindings(db):
    table = 'v1_percent_' + uuid4().hex
    db.execute(f'CREATE TABLE "{table}" (id int PRIMARY KEY, value text)')
    db.execute(f'INSERT INTO "{table}" VALUES (1, :a), (2, :b), (3, :c)', {'a': 'abc', 'b': 'xa%', 'c': 'b'})
    # No parameters: execution still passes a mapping, so PyMySQL reads %% as %.
    rows = db.execute(f'SELECT id, 7 % 3 AS r FROM "{table}" /* 50% */ WHERE value LIKE \'a%\' -- 100%\n'
                      '# 5%\nORDER BY id').fetchall()
    assert [dict(row) for row in rows] == [{'id': 1, 'r': 1}]
    rows = db.execute(f'SELECT id FROM "{table}" WHERE value LIKE :p AND value LIKE \'%a%\' -- :q 1%',
                      {'p': 'x%'}).fetchall()
    assert [dict(row) for row in rows] == [{'id': 2}]
    db.rollback()


def test_metadata_mismatch_rolls_back_prior_write(db):
    table = 'v1_runtime_' + uuid4().hex
    db.execute(f'CREATE TABLE "{table}" (id int PRIMARY KEY)')
    db.commit()
    with pytest.raises(ValueError, match='Compiled result columns'):
        with completed(db) as tx:
            tx.execute(CompiledQuery(f'INSERT INTO "{table}" VALUES (1)', dialect='mysql', binding='pymysql_named'))
            tx.execute(CompiledQuery('SELECT 1 AS actual', columns=(ResultColumn('wrong'),),
                                     dialect='mysql', binding='pymysql_named'))
    assert [dict(row) for row in db.execute(f'SELECT count(*) AS n FROM "{table}"').fetchall()] == [{'n': 0}]


def test_values_round_trip(db):
    table = 'v1_types_' + uuid4().hex
    db.execute(f'CREATE TABLE "{table}" (id int PRIMARY KEY, flag boolean, small tinyint, at time, '
               f'day date, moment datetime(6), amount decimal(10,2), name varchar(20))')
    values = {'id': 1, 'flag': False, 'small': 7, 'at': time(23, 59, 1), 'day': date(2026, 10, 26),
              'moment': datetime(2026, 10, 26, 8, 30, 0, 123456), 'amount': Decimal('12.50'), 'name': 'Àé'}
    db.execute(f'INSERT INTO "{table}" VALUES (:id, :flag, :small, :at, :day, :moment, :amount, :name)', values)
    row, = db.execute(f'SELECT * FROM "{table}" WHERE flag IS FALSE AND name ILIKE :n', {'n': 'àé'}).fetchall()
    assert dict(row) == values
    assert type(dict(row)['flag']) is bool and type(dict(row)['small']) is int
    db.rollback()


def test_unsupported_operations(db):
    with pytest.raises(UnsupportedFeatureError, match='deferred constraints'):
        db.setConstraintsDeferred()
    with pytest.raises(UnsupportedFeatureError, match='analyze'):
        db.analyze()
