"""Error ownership across named connections and preservation during DB cleanup."""
import pytest

from asqueel import CompiledQuery, SqlTable, TransactionStateError
from tests.application_connections.test_deferred import database


@pytest.mark.parametrize('hook', ['trigger_onInserting', 'trigger_onInserted'])
def test_sql_error_on_another_connection_cannot_commit_incomplete_outer_write(hook):
    def fail(self, record):
        with self.db.tempEnv(connectionName='B'):
            self.db.execute(CompiledQuery('fail'))

    item_class = type('Item', (SqlTable,), {hook: fail})
    db = database(item_class)
    try:
        events = []
        db.execute(CompiledQuery('earlier A'))
        db.deferAfterCommit(lambda: events.append('A committed'))
        with db.tempEnv(connectionName='C'):
            db.execute(CompiledQuery('independent C'))
        with pytest.raises(LookupError, match='statement failed'):
            db.table('app.item').insert({'id': 1})
        assert db.currentTrigger is None
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        assert db.adapter.persisted == []
        assert events == []
        # A failed domain operation on A must not poison independent C or the
        # already rolled-back B. Both can still complete their own work.
        with db.tempEnv(connectionName='C'):
            db.commit()
        with db.tempEnv(connectionName='B'):
            db.execute(CompiledQuery('recovered B'))
            db.commit()
        db.rollback()
        assert db.adapter.persisted == ['independent C', 'recovered B']
        assert events == []
    finally:
        db.closeConnection()


def test_reused_exception_from_an_earlier_sql_attempt_is_a_new_hook_failure():
    original = LookupError('same exception instance')

    class Item(SqlTable):
        def trigger_onInserting(self, record):
            raise original

    def sql_failure():
        raise original

    db = database(Item)
    try:
        db.adapter.callback = sql_failure
        with pytest.raises(LookupError) as caught:
            db.execute(CompiledQuery('first attempt'))
        assert caught.value is original
        db.adapter.callback = None
        with pytest.raises(LookupError) as caught:
            db.table('app.item').insert({'id': 1})
        assert caught.value is original
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        db.rollback()
        db.execute(CompiledQuery('recovered'))
        db.commit()
        assert db.adapter.persisted == ['recovered']
    finally:
        db.closeConnection()

