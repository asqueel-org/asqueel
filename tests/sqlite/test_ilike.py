"""SQLite ILIKE adaptation shared by the two existing compiler profiles."""
import sqlite3

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler


@pytest.fixture(params=['native', 'objects_tree'])
def database(request, tmp_path):
    path = tmp_path / 'ilike.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT, ilike_label TEXT)')
        connection.executemany('INSERT INTO customer VALUES (?,?,?)',
                               [(1, 'Alice', 'cliente A'), (2, 'Bob', 'cliente B')])
    config = SqlDatabaseConfig()
    root = config.source.db('ilike_test', implementation='sqlite', conninfo=str(path))
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('customer', pkey='id')
    table.column('id', dtype='L')
    table.column('name', dtype='T')
    table.column('ilike_label', dtype='T')
    db = (config.render() if request.param == 'native' else
          SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)))
    try:
        yield db
    finally:
        db.closeConnection()


@pytest.mark.parametrize('operator', ['ILIKE', 'ilike', 'IlIkE', 'NOT ILIKE'])
def test_ilike_operator_executes_in_both_compilers(database, operator):
    query = database.table('app.customer').query('$name', where=f'$name {operator} :pattern', pattern='ali%')
    assert ' ILIKE ' not in query.compiled.sql.upper()
    assert query.compiled.params == {'pattern': 'ali%'}
    assert [row['name'] for row in query.fetch()] == (['Bob'] if operator.startswith('NOT') else ['Alice'])


def test_column_containing_ilike_is_unchanged(database):
    query = database.table('app.customer').query('$ilike_label', where='$id=:id', id=1)
    assert '"t0"."ilike_label"' in query.compiled.sql
    assert query.fetch()[0]['ilike_label'] == 'cliente A'


def test_operator_does_not_change_column_literal_or_binding(database):
    query = database.table('app.customer').query(
        "$ilike_label, 'ILIKE' AS operator_name",
        where='$ilike_label ILIKE :ilike', ilike='CLIENTE A')
    assert query.compiled.params == {'ilike': 'CLIENTE A'}
    row = query.fetch()[0]
    assert row['ilike_label'] == 'cliente A'
    assert row['operator_name'] == 'ILIKE'
