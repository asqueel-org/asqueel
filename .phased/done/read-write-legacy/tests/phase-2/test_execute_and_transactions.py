"""db.execute returning the cursor, autocommit, onDbCommitted and the database maintenance calls as legacy (Macro 6, Phase 2)."""
import pytest

from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


def declare(pkg):
    note = pkg.table('note', pkey='id')
    note.column('id', size=':22')
    note.column('text')
    note.column('amount', dtype='L')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        db.table('app.note').sql_insert([{'id': 'a', 'text': 'x', 'amount': 1},
                                         {'id': 'b', 'text': 'y', 'amount': 2}])
        db.commit()
        yield db


def sqltable(db):
    model = db.table('app.note').model
    return f'{model.sqlschema}.{model.sqlname}'


def note_sql(db):
    return f'SELECT id, text FROM {sqltable(db)} ORDER BY id'


def test_execute_returns_the_cursor_with_rows_read_by_name(db):
    cursor = db.execute(note_sql(db))
    rows = cursor.fetchall()
    assert [row['id'] for row in rows] == ['a', 'b']
    assert rows[1]['text'] == 'y'
    assert [column[0] for column in cursor.description] == ['id', 'text']


def test_execute_returns_the_cursor_of_a_write_with_its_rowcount(db):
    table = sqltable(db)
    cursor = db.execute(f'UPDATE {table} SET text=:t WHERE id=:pk', {'t': 'z', 'pk': 'a'})
    assert cursor.rowcount == 1


def test_execute_with_autocommit_commits_the_connection(db):
    table = sqltable(db)
    db.execute(f"UPDATE {table} SET text='kept' WHERE id='a'", autocommit=True)
    db.rollback()
    assert db.table('app.note').query(columns='$text', where='$id=:pk', pk='a').fetchRecord()['text'] == 'kept'


def test_execute_refuses_another_store_and_accepts_the_table(db):
    with pytest.raises(UnsupportedFeatureError, match='storename'):
        db.execute(note_sql(db), storename='other')
    assert len(db.execute(note_sql(db), dbtable='app.note').fetchall()) == 2


def test_on_db_committed_runs_once_after_every_commit(db):
    calls = []
    db.onDbCommitted = lambda: calls.append(len(calls))
    db.table('app.note').insert({'id': 'c', 'text': 'w'})
    db.commit()
    assert calls == [0]
    db.commit()
    assert calls == [0, 1]


def test_analyze_and_vacuum_keep_the_data(db):
    db.analyze()
    db.commit()
    db.vacuum()
    db.vacuum(table=sqltable(db))
    assert db.table('app.note').query(columns='$id').fetchPkeys() == ['a', 'b']


def test_set_locale_hands_the_environment_locale_to_the_adapter(db, monkeypatch):
    seen = []
    monkeypatch.setattr(type(db.adapter), 'setLocale', lambda _adapter, locale: seen.append(locale))
    db.setLocale()
    assert seen == []
    db.locale = 'it_IT'
    db.setLocale()
    assert seen == ['it_IT']


def test_set_constraints_deferred_lets_a_child_precede_its_parent():
    # wf:contract: with a foreign key app.line.note_id -> app.note.id migrated on the dialect,
    # wf:contract: db.setConstraintsDeferred() followed by inserting the line before its note
    # wf:contract: commits without error on PostgreSQL and SQLite; without the call the same
    # wf:contract: order raises the driver's integrity error at insert or at commit
    pytest.fail('phase 2 pending')


def test_an_error_while_fetching_from_a_cursor_rolls_back_the_connection():
    # wf:contract: an uncommitted insert, then a cursor from db.execute whose second row raises
    # wf:contract: a driver error during fetch (SQLite: abs() of -9223372036854775808; PostgreSQL:
    # wf:contract: a division by zero reached on the second row of a server cursor) re-raises
    # wf:contract: the driver error, rolls the connection back (the insert is gone) and leaves
    # wf:contract: the database usable for the next query, as an error raised by execute does
    pytest.fail('phase 2 pending')
