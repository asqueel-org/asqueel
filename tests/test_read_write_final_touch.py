"""Read-write cycle corrections after the Macro 6 review: open cursors released by
closeConnection, fetch errors of a stale cursor, pending exceptions per named
connection, query delete over a cascade, typed composite keys, vacuum with pending
work, database-generated pkeys and session cleanup."""
from datetime import date, datetime
import sqlite3

import psycopg
import pytest

from asqueel import TransactionStateError, session
from asqueel.environment import SqlEnvironment
from asqueel.errors import DeferredCommitError
from asqueel.runtime import Database
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


def declare(pkg):
    note = pkg.table('note', pkey='id')
    note.column('id', size=':22')
    note.column('text')
    node = pkg.table('node', pkey='id')
    node.column('id', size=':22')
    node.column('parent_id', size=':22').relation('app.node.id', onDelete='cascade')
    mixed = pkg.table('mixed', pkey='key')
    mixed.column('num', dtype='I')
    mixed.column('day', dtype='D')
    mixed.column('ts', dtype='DH')
    mixed.column('flag', dtype='B')
    mixed.column('text')
    mixed.compositeColumn('key', columns='num,day,ts,flag')
    numbered = pkg.table('numbered', pkey='id')
    numbered.column('id', dtype='L', sql_default='100')
    numbered.column('text')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        yield db


def count(db, table, where=None, **params):
    return db.table(table).query(where=where, **params).count()


def test_close_connection_closes_an_unread_cursor_so_the_next_write_commits(db):
    db.table('app.note').insert({'id': 'n1'})
    db.commit()
    unread = db.execute(f'SELECT id FROM {db.table("app.note").model.sqlschema}.note')
    db.closeConnection()
    db.table('app.note').insert({'id': 'n2'})
    db.commit()
    assert count(db, 'app.note') == 2
    del unread  # referenced until here: closeConnection had to close it


def test_a_fetch_error_on_a_cursor_from_before_close_connection_leaves_the_new_transaction(db):
    db.table('app.note').insert({'id': 'n1'})
    db.commit()
    cursor = db.table('app.note').query(columns='$id').cursor()
    db.closeConnection()
    calls = []
    db.table('app.note').insert({'id': 'n2'})
    db.deferToCommit(lambda: calls.append('to_commit'))
    db.deferredRaise(ValueError('kept'))
    with pytest.raises((sqlite3.Error, psycopg.Error)):
        cursor.fetchall()
    with pytest.raises(DeferredCommitError, match='kept'):
        db.commit()
    assert calls == ['to_commit']


def test_pending_exceptions_belong_to_their_named_connection(db, tmp_path):
    if db.implementation == 'sqlite':
        db.config.builder.source[db.config.root_label].connection(
            'aux', database=str(tmp_path / 'options.sqlite'))
    assert db.currentEnv.get('_pendingExceptions__main_db__main_connection') is None
    db.table('app.note').insert({'id': 'n1'})
    db.deferredRaise(ValueError('main fails'))
    assert len(db.currentEnv['_pendingExceptions__main_db__main_connection']) == 1
    with db.tempEnv(connectionName='aux'):
        db.rollback()
        db.execute('SELECT 1').close()
        with pytest.raises((sqlite3.Error, psycopg.Error)):
            db.execute('SELECT * FROM missing_table')
        db.rollback()
        db.execute('SELECT 1').close()
        db.commit()
    with pytest.raises(DeferredCommitError, match='main fails'):
        db.commit()
    db.rollback()


def test_query_delete_skips_a_row_already_removed_by_a_cascade(db):
    table = db.table('app.node')
    table.insert({'id': 'p'})
    table.insert({'id': 'q', 'parent_id': 'p'})
    db.commit()
    rows = table.query(order_by='$id').delete()
    assert [row['id'] for row in rows] == ['p', 'q']
    db.commit()
    assert count(db, 'app.node') == 0


def test_the_composite_column_value_with_typed_members_is_a_key_for_update_and_delete(db):
    table = db.table('app.mixed')
    table.insert({'num': 7, 'day': date(2026, 1, 2), 'ts': datetime(2026, 1, 2, 10, 30),
                  'flag': True, 'text': 'a'})
    db.commit()
    key = table.query(columns='$key').fetchRecord()['key']
    table.update({'text': 'b'}, pkey=key)
    assert table.query(columns='$text').fetchRecord()['text'] == 'b'
    table.delete(key)
    assert count(db, 'app.mixed') == 0


def test_vacuum_refuses_pending_work_and_runs_after_commit(db):
    db.table('app.note').insert({'id': 'n1'})
    with pytest.raises(TransactionStateError, match='vacuum requires no pending work'):
        db.vacuum()
    db.commit()
    db.vacuum()
    assert count(db, 'app.note') == 1


def test_insert_leaves_a_pkey_with_sql_default_to_the_database(db):
    table = db.table('app.numbered')
    table.insert({'id': 1, 'text': 'first'})
    record = table.insert({'text': 'second'})
    assert record['id'] == 100
    assert count(db, 'app.numbered', where='$id = 100') == 1


def failing_close():
    raise RuntimeError('cleanup')


def test_session_keeps_the_body_error_when_cleanup_also_fails(db):
    try:
        with pytest.raises(ValueError, match='body') as caught:
            with session(db):
                db.closeConnection = failing_close
                raise ValueError('body')
    finally:
        del db.closeConnection
    assert caught.value.__notes__ == ['Connection cleanup failed: RuntimeError']


def test_session_propagates_a_cleanup_failure_after_a_successful_body(db):
    try:
        with pytest.raises(RuntimeError, match='cleanup'):
            with session(db):
                db.closeConnection = failing_close
    finally:
        del db.closeConnection


def test_session_requires_a_writable_environment(tmp_path):
    db = Database(str(tmp_path / 'readonly.sqlite'), environment=SqlEnvironment())
    with pytest.raises(TransactionStateError, match='requires a writable environment'):
        with session(db):
            pass
