"""Connection lifecycle: session(db) as alias of db.session(), close/with only on a SessionDb, no acquire/outcome, deferred calls in currentEnv (Macro 6, Phase 1)."""
import pytest

import asqueel
from asqueel import AsqueelDb, SessionDb, TransactionStateError, session
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

DEFER_KEY = 'to_commit_defer_calls__main_db__main_connection'
AFTER_KEY = 'after_commit_defer_calls__main_db__main_connection'


def declare(pkg):
    note = pkg.table('note', pkey='id')
    note.column('id', size=':22')
    note.column('text')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        yield db


def count(db):
    return db.table('app.note').query(columns='$id').count()


def test_the_connection_api_has_no_acquire_or_outcome_and_only_a_session_is_a_context_manager():
    for name in ('acquire', 'outcome', '__enter__', '__exit__'):
        assert not hasattr(AsqueelDb, name), name
    for name in ('close', '__enter__', '__exit__'):
        assert hasattr(SessionDb, name), name
    assert not hasattr(asqueel, 'DatabaseClosedError')


def test_session_clears_the_environment_and_applies_the_initial_values(db):
    db.updateEnv(user='old', tenant='t1')
    db.close()
    with session(db.shared, user='ada') as opened:
        assert opened is not db and opened.shared is db.shared
        assert opened.currentEnv == {'user': 'ada'}
    with session(db.shared) as opened:
        assert opened.currentEnv == {}


def test_session_exit_closes_the_connection_and_drops_uncommitted_work(db):
    db.close()
    with session(db.shared) as opened:
        opened.table('app.note').insert({'id': 'kept', 'text': 'a'})
        opened.commit()
        opened.table('app.note').insert({'id': 'lost', 'text': 'b'})
    with session(db.shared) as opened:
        assert opened.table('app.note').query(columns='$id').fetchPkeys() == ['kept']


def test_session_exit_closes_the_connection_when_the_body_raises(db):
    db.close()
    with pytest.raises(RuntimeError, match='boom'):
        with session(db.shared) as opened:
            opened.table('app.note').insert({'id': 'lost', 'text': 'b'})
            raise RuntimeError('boom')
    with session(db.shared) as opened:
        assert count(opened) == 0


def test_a_nested_session_of_the_same_call_is_the_open_one_and_refuses_new_values(db):
    db.close()
    with session(db.shared) as opened:
        opened.table('app.note').insert({'id': 'n1', 'text': 'a'})
        with pytest.raises(TransactionStateError, match='session'):
            session(db.shared, user='nested')
        assert session(db.shared) is opened
        assert count(opened) == 1
        opened.commit()
    with session(db.shared) as opened:
        assert count(opened) == 1


def test_close_connection_rolls_back_and_the_database_stays_usable(db):
    db.table('app.note').insert({'id': 'lost', 'text': 'b'})
    db.closeConnection()
    assert count(db) == 0
    db.table('app.note').insert({'id': 'kept', 'text': 'a'})
    db.commit()
    assert count(db) == 1


def test_deferred_calls_live_in_currentEnv_per_connection_key(db):
    calls = []
    db.deferToCommit(calls.append, 'before')
    db.deferAfterCommit(calls.append, 'after')
    assert DEFER_KEY in db.currentEnv
    assert AFTER_KEY in db.currentEnv
    db.table('app.note').insert({'id': 'n1', 'text': 'a'})
    db.commit()
    assert calls == ['before', 'after']


def test_clearCurrentEnv_drops_the_pending_deferred_calls(db):
    calls = []
    db.table('app.note').insert({'id': 'n1', 'text': 'a'})
    db.deferToCommit(calls.append, 'before')
    db.clearCurrentEnv()
    db.commit()
    assert calls == []
    assert count(db) == 1


def test_defer_to_commit_with_the_same_id_returns_the_kwargs_to_accumulate(db):
    seen = []

    def collect(items=None):
        seen.append(list(items))

    first = db.deferToCommit(collect, items=['a'], _deferredId='one')
    second = db.deferToCommit(collect, items=['b'], _deferredId='one')
    assert second is first
    second['items'].append('b')
    db.table('app.note').insert({'id': 'n1', 'text': 'a'})
    db.commit()
    assert seen == [['a', 'b']]
