"""SQLite binding, result and lifecycle boundaries on the stdlib driver adapter."""
import sqlite3

import pytest

from asqueel import CompiledQuery, ResultColumn
from asqueel.runtime import Database


def test_adapter_is_loaded_into_the_same_runtime():
    db = Database(':memory:', implementation='sqlite')
    try:
        db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, value TEXT)')
        db.commit()
        value = "'); DROP TABLE item; -- 50%"
        result = db.execute('INSERT INTO item VALUES (:id, :value) RETURNING value', {'id': 1, 'value': value})
        assert [dict(row) for row in result.fetchall()] == [{'value': value}]
        db.rollback()
        assert db.execute('SELECT * FROM item').fetchall() == []
        db.commit()
    finally:
        db.closeConnection()


@pytest.mark.parametrize('sql', ["SELECT '50% :fake' AS label, :value AS value",
                               'SELECT :value AS `:identifier`',
                               'SELECT :value AS [:identifier]'])
def test_binding_protects_sqlite_literals_and_identifiers(sql):
    db = Database(':memory:', implementation='sqlite')
    try:
        result = db.execute(sql, {'value': "O'Reilly"})
        assert "O'Reilly" in result.fetchall()[0].values()
    finally:
        db.closeConnection()


def test_invalid_profile_does_not_connect_and_missing_binding_becomes_null():
    db = Database(':memory:', implementation='sqlite')
    driver = db.adapter
    with pytest.raises(ValueError, match='profile'):
        db.execute(CompiledQuery('SELECT 1'))
    assert db._connection_state['connection'] is None
    compiled = driver.prepare_sql('SELECT :missing', {}, {})
    assert compiled.sql == 'SELECT :missing'
    assert compiled.params == {'missing': None}
    assert db._connection_state['connection'] is None
    rows = db.execute(compiled).fetchall()
    assert len(rows) == 1
    assert rows[0][0] is None
    db.closeConnection()


@pytest.mark.parametrize('sql,columns,message', [
    ('SELECT 1 AS same, 2 AS same', (), 'unique names'),
    ('SELECT 1 AS actual', (ResultColumn('wrong'),), 'match cursor'),
    ('CREATE TABLE item (id integer)', (ResultColumn('id'),), 'without a result set'),
])
def test_result_metadata_failures_roll_back(sql, columns, message):
    db = Database(':memory:', implementation='sqlite')
    try:
        with pytest.raises(ValueError, match=message):
            db.execute(CompiledQuery(sql, columns=columns, dialect='sqlite', binding='sqlite_named'))
        assert not db._connection_state['pending']
    finally:
        db.closeConnection()


def test_native_foreign_key_failure_rolls_back_prior_work():
    db = Database(':memory:', implementation='sqlite')
    try:
        db.execute('CREATE TABLE parent (id integer primary key)')
        db.execute('CREATE TABLE child (id integer primary key, parent_id integer references parent(id))')
        db.commit()
        db.execute('INSERT INTO parent VALUES (1)')
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO child VALUES (1, 99)')
        assert db.execute('SELECT * FROM parent').fetchall() == []
    finally:
        db.closeConnection()


def test_direct_prepared_query_preserves_parameters_and_checks_metadata():
    db = Database(':memory:', implementation='sqlite')
    driver = db.adapter
    metadata = (ResultColumn('value', 'T', 'app.item.value'),)
    from dataclasses import replace
    query = replace(driver.prepare_sql('SELECT :v AS value', {'v': 'data'}, {}), columns=metadata)
    assert dict(query.params) == {'v': 'data'}
    try:
        assert [dict(row) for row in db.execute(query).fetchall()] == [{'value': 'data'}]
    finally:
        db.closeConnection()
