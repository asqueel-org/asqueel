"""Error ownership across named connections and preservation during DB cleanup."""
import pytest

from asqueel import CompiledQuery, TransactionStateError
from tests.application_connections.test_deferred import database


@pytest.mark.parametrize('hook', ['trigger_onInserting', 'trigger_onInserted'])
def test_sql_error_on_another_connection_cannot_commit_incomplete_outer_write(hook, tmp_path):
    db = database(tmp_path / 'app', f'''
        def {hook}(self, record):
            self.db.session('B').execute(CompiledQuery('fail'))
    ''')
    try:
        events = []
        db.execute(CompiledQuery('earlier A'))
        db.deferAfterCommit(lambda: events.append('A committed'))
        c = db.session('C')
        c.execute(CompiledQuery('independent C'))
        with pytest.raises(LookupError, match='statement failed'):
            db.table('app.item').insert({'id': 1})
        assert db.currentTrigger is None
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        assert db.adapter.persisted == []
        assert events == []
        # A failed domain operation on A must not poison independent C or the
        # already rolled-back B. Both can still complete their own work.
        c.commit()
        b = db.session('B')
        b.execute(CompiledQuery('recovered B'))
        b.commit()
        db.rollback()
        assert db.adapter.persisted == []
        assert c.adapter.persisted == ['independent C']
        assert b.adapter.persisted == ['recovered B']
        assert events == []
    finally:
        db.closeConnection()


def test_reused_exception_from_an_earlier_sql_attempt_is_a_new_hook_failure(tmp_path):
    original = LookupError('same exception instance')

    def sql_failure():
        raise original

    db = database(tmp_path / 'app', '''
        original = None

        def trigger_onInserting(self, record):
            raise self.original
    ''')
    db.table('app.item').original = original
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

