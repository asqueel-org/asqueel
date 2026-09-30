"""Error ownership across named sessions and preservation during DB cleanup."""
import pytest

from asqueel import CompiledQuery, SqlTable, TransactionStateError
from tests.application_session.test_deferred import database


@pytest.mark.parametrize('hook', ['trigger_onInserting', 'trigger_onInserted'])
def test_sql_error_on_another_connection_cannot_commit_incomplete_outer_write(hook):
    def fail(self, record):
        with self.db.tempEnv(connectionName='B'):
            self.db.execute(CompiledQuery('fail'))

    item_class = type('Item', (SqlTable,), {hook: fail})
    with database(item_class) as db:
        events = []
        db.execute(CompiledQuery('earlier A'))
        db.deferAfterCommit(lambda: events.append('A committed'))
        with db.tempEnv(connectionName='C'):
            db.execute(CompiledQuery('independent C'))
        with pytest.raises(LookupError, match='statement failed'):
            db.table('item').insert({'id': 1})
        assert db.currentTrigger is None
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        assert db.driver.persisted == []
        assert events == []
        # A failed domain operation on A must not poison independent C or the
        # already rolled-back B. Both can still complete their own work.
        with db.tempEnv(connectionName='C'):
            db.commit()
        with db.tempEnv(connectionName='B'):
            db.execute(CompiledQuery('recovered B'))
            db.commit()
        db.rollback()
        assert db.driver.persisted == ['independent C', 'recovered B']
        assert events == []


def test_reused_exception_from_an_earlier_sql_attempt_is_a_new_hook_failure():
    original = LookupError('same exception instance')

    class Item(SqlTable):
        def trigger_onInserting(self, record):
            raise original

    def sql_failure():
        raise original

    with database(Item) as db:
        db.driver.callback = sql_failure
        with pytest.raises(LookupError) as caught:
            db.execute(CompiledQuery('first attempt'))
        assert caught.value is original
        db.driver.callback = None
        with pytest.raises(LookupError) as caught:
            db.table('item').insert({'id': 1})
        assert caught.value is original
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        db.rollback()
        db.execute(CompiledQuery('recovered'))
        db.commit()
        assert db.driver.persisted == ['recovered']


@pytest.mark.parametrize('cleanup', ['rollback', 'close'])
def test_db_context_preserves_hook_exception_when_cleanup_also_fails(cleanup):
    original = ValueError('original hook failure')
    cleanup_error = OSError('cleanup failed')

    class Item(SqlTable):
        def trigger_onInserted(self, record):
            raise original

    db = database(Item)
    setattr(db.driver, cleanup + '_error', cleanup_error)
    with pytest.raises(ValueError) as caught:
        with db:
            db.table('item').insert({'id': 1})
    assert caught.value is original
    assert caught.value.__cause__ is cleanup_error
    assert any('cleanup' in note.lower() for note in caught.value.__notes__)
    assert db.driver.persisted == []
    assert db.driver.calls[-1] == 'close'
    assert db._closed


def test_successful_db_context_still_reports_cleanup_failure():
    db = database()
    db.driver.rollback_error = OSError('cleanup failed')
    with pytest.raises(OSError, match='cleanup failed'):
        with db:
            db.execute(CompiledQuery('pending'))
    assert db._closed
