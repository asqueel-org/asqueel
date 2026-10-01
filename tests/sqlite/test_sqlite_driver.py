"""SQLite binding, result and lifecycle boundaries on the stdlib driver."""
import sqlite3

import pytest

from asqueel import CompiledQuery, ResultColumn
from asqueel.drivers.sqlite import SqliteDriver
from asqueel.query_plan import Parameter, SqlStatement
from asqueel.runtime import Database


def test_driver_is_injected_into_the_same_runtime():
    db = Database(':memory:', driver=SqliteDriver())
    try:
        db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, value TEXT)')
        db.commit()
        value = "'); DROP TABLE item; -- 50%"
        result = db.execute('INSERT INTO item VALUES (:id, :value) RETURNING value', {'id': 1, 'value': value})
        assert result.rows == [{'value': value}]
        db.rollback()
        assert db.execute('SELECT * FROM item').rows == []
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize('sql', ["SELECT '50% :fake' AS label, :value AS value",
                               'SELECT :value AS `:identifier`',
                               'SELECT :value AS [:identifier]'])
def test_binding_protects_sqlite_literals_and_identifiers(sql):
    db = Database(':memory:', driver=SqliteDriver())
    try:
        result = db.execute(sql, {'value': "O'Reilly"})
        assert "O'Reilly" in result.rows[0].values()
    finally:
        db.close()


def test_invalid_profile_and_missing_parameters_do_not_connect():
    driver = SqliteDriver()
    db = Database(':memory:', driver=driver)
    with pytest.raises(ValueError, match='profile'):
        db.execute(CompiledQuery('SELECT 1'))
    with pytest.raises(ValueError, match='Missing'):
        db.execute('SELECT :missing')
    assert db._connection_state['connection'] is None
    db.close()


@pytest.mark.parametrize('statement,error', [
    ('text', TypeError),
    (SqlStatement(('SELECT 1',)), ValueError),
    (SqlStatement((Parameter('bad-name'),), dialect='sqlite'), ValueError),
    (SqlStatement((Parameter('missing'),), dialect='sqlite'), ValueError),
    (SqlStatement((object(),), dialect='sqlite'), TypeError),
])
def test_prepare_rejects_invalid_statement(statement, error):
    with pytest.raises(error):
        SqliteDriver().prepare(statement)


@pytest.mark.parametrize('sql,columns,message', [
    ('SELECT 1 AS same, 2 AS same', (), 'unique names'),
    ('SELECT 1 AS actual', (ResultColumn('wrong'),), 'match cursor'),
    ('CREATE TABLE item (id integer)', (ResultColumn('id'),), 'without a result set'),
])
def test_result_metadata_failures_roll_back(sql, columns, message):
    db = Database(':memory:', driver=SqliteDriver())
    try:
        with pytest.raises(ValueError, match=message):
            db.execute(CompiledQuery(sql, columns=columns, dialect='sqlite', binding='sqlite_named'))
        assert db.outcome == 'rolled_back'
    finally:
        db.close()


def test_native_foreign_key_failure_rolls_back_prior_work():
    db = Database(':memory:', driver=SqliteDriver())
    try:
        db.execute('CREATE TABLE parent (id integer primary key)')
        db.execute('CREATE TABLE child (id integer primary key, parent_id integer references parent(id))')
        db.commit()
        db.execute('INSERT INTO parent VALUES (1)')
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO child VALUES (1, 99)')
        assert db.execute('SELECT * FROM parent').rows == []
    finally:
        db.close()


def test_direct_prepared_query_preserves_parameters_and_metadata():
    driver = SqliteDriver()
    metadata = (ResultColumn('value', 'T', 'app.item.value'),)
    query = driver.prepare(SqlStatement(('SELECT ', Parameter('v'), ' AS value'),
                                        {'v': 'data', 'unused': 'ignored'}, metadata, dialect='sqlite'))
    assert dict(query.params) == {'v': 'data'}
    db = Database(':memory:', driver=driver)
    try:
        assert db.execute(query).columns == metadata
    finally:
        db.close()
