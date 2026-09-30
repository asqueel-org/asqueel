"""Commit lifecycle contracts, including failures hidden inside callbacks."""
import pytest

from genro_sql import CompiledQuery, DeferredCommitError, SqlTable, TransactionStateError, build_database
from genro_sql.session import Session
from tests.application_config.test_application import Recipe
from tests.application_session.test_session import Driver


def database(table_class=SqlTable):
    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = table_class
    return build_database(recipe, driver=Driver())


def test_hooks_can_register_both_queues_and_deferred_errors():
    events = []

    class Item(SqlTable):
        def trigger_onInserting(self, record):
            self.db.deferToCommit(lambda: events.append(('before', self.db.outcome)))
            self.db.deferAfterCommit(lambda: events.append(('after', self.db.outcome)))
            if record['id'] == 2:
                self.db.deferredRaise(ValueError('invalid record'))

    with database(Item) as db:
        db.table('item').insert({'id': 1})
        assert events == []
        db.commit()
        assert events == [('before', 'active'), ('after', 'committed')]
        db.table('item').insert({'id': 2})
        with pytest.raises(DeferredCommitError, match='invalid record'):
            db.commit()
        db.rollback()
        assert events[-1] == ('before', 'active')
        assert db.driver.calls.count('commit') == 1


def test_precommit_failure_rolls_back_atomic_scope_and_clears_callbacks():
    driver = Driver()
    session = Session(driver)
    events = []

    def fail():
        raise ValueError('pre-commit')

    with pytest.raises(ValueError, match='pre-commit'):
        with session.transaction():
            session.execute(CompiledQuery('write'))
            session.defer_to_commit(fail)
            session.defer_after_commit(lambda: events.append('after'))
    assert driver.calls[-1] == 'rollback'
    assert not driver.persisted
    session.execute(CompiledQuery('recovery'))
    session.commit()
    assert driver.persisted == ['recovery']
    assert events == []
    session.close()


@pytest.mark.parametrize('queue', ['before', 'after'])
def test_caught_sql_error_cannot_continue_commit_or_callbacks(queue):
    driver = Driver()
    session = Session(driver)
    events = []
    session.execute(CompiledQuery('write'))

    def fail():
        try:
            session.execute(CompiledQuery('fail'))
        except LookupError:
            pass
        # Even a fresh registration must not resurrect the aborted commit.
        session.defer_after_commit(lambda: events.append('resurrected'))

    register = session.defer_to_commit if queue == 'before' else session.defer_after_commit
    register(fail)
    register(lambda: events.append('later'))
    with pytest.raises(TransactionStateError):
        session.commit()
    assert driver.calls.count('commit') == (queue == 'after')
    assert driver.persisted == (['write'] if queue == 'after' else [])
    assert events == []
    session.rollback()
    session.execute(CompiledQuery('recovery'))
    session.commit()
    assert events == []
    session.close()


def test_caught_domain_failure_in_callback_cannot_be_committed():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('write'))
    session.defer_to_commit(session.mark_failed)
    with pytest.raises(TransactionStateError):
        session.commit()
    assert driver.persisted == []
    session.rollback()
    session.close()


def test_callback_context_pins_scope_connection_and_restores_environment():
    with database() as db:
        events = []
        # Scope owns A even if the environment is changed before scope exit.
        with db.tempEnv(connectionName='A', onCommittingStep=False):
            with db.transaction():
                db.execute(CompiledQuery('A'))
                db.deferToCommit(lambda: events.append((db.currentConnectionName, db.currentEnv['onCommittingStep'])))
                db.deferAfterCommit(lambda: events.append((db.currentConnectionName, db.currentEnv['onCommittingStep'])))
                db.currentEnv['connectionName'] = 'B'
            assert db.currentConnectionName == 'B'
            assert db.currentEnv['onCommittingStep'] is False
        assert events == [('A', True), ('A', True)]


def test_named_queues_and_exceptions_are_independent():
    with database() as db:
        events = []
        db.execute(CompiledQuery('main'))
        db.deferToCommit(lambda: events.append('main'))
        db.deferredRaise(ValueError('main error'))
        with db.tempEnv(connectionName='other'):
            db.execute(CompiledQuery('other'))
            db.deferToCommit(lambda: events.append('other'))
            db.deferAfterCommit(lambda: events.append('other after'))
            db.commit()
        assert events == ['other', 'other after']
        assert db.driver.persisted == ['other']
        with pytest.raises(DeferredCommitError):
            db.commit()
        db.rollback()
        assert events == ['other', 'other after', 'main']


@pytest.mark.parametrize('completion', ['rollback', 'close'])
def test_discard_clears_queues_even_without_sql(completion):
    session = Session(Driver())
    events = []
    session.defer_to_commit(lambda: events.append('before'))
    session.defer_after_commit(lambda: events.append('after'))
    session.deferred_raise(ValueError('discard'))
    getattr(session, completion)()
    if completion == 'rollback':
        session.execute(CompiledQuery('new'))
        session.commit()
    assert events == []
    session.close()


def test_unknown_commit_never_dispatches_after_and_discards_queue():
    driver = Driver()
    session = Session(driver)
    events = []
    session.execute(CompiledQuery('write'))
    session.defer_after_commit(lambda: events.append('after'))
    driver.commit_error = OSError('unknown commit')
    with pytest.raises(OSError):
        session.commit()
    assert session.outcome == 'unknown'
    assert events == []
    driver.commit_error = None
    session.rollback()
    session.execute(CompiledQuery('next'))
    session.commit()
    assert events == []
    session.close()


def test_after_callback_can_start_next_transaction_as_in_legacy():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('first'))
    session.defer_after_commit(lambda: session.execute(CompiledQuery('second')))
    session.commit()
    assert driver.persisted == ['first', 'second']
    assert driver.calls.count('commit') == 2
    session.close()


@pytest.mark.parametrize('action', ['commit', 'rollback', 'close'])
def test_callback_cannot_reenter_transaction_completion(action):
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('write'))
    session.defer_to_commit(getattr(session, action))
    with pytest.raises(TransactionStateError):
        session.commit()
    assert not driver.persisted
    session.rollback()
    session.close()


def test_stack_tracks_nested_writes_and_restores_after_exception():
    events = []

    class Item(SqlTable):
        def trigger_onInserting(self, record):
            current = self.currentTrigger
            events.append((current.event, current.table, current.level,
                           current.parent.record['id'] if current.parent else None))
            if record['id'] == 1:
                self.insert({'id': 2})
                assert self.currentTrigger is current
            elif record['id'] == 3:
                raise ValueError('hook')

    with database(Item) as db:
        db.table('item').insert({'id': 1})
        assert db.currentTrigger is None
        assert events == [('insert', 'app.item', 0, None), ('insert', 'app.item', 1, 1)]
        db.commit()
        with pytest.raises(ValueError):
            db.table('item').insert({'id': 3})
        assert db.currentTrigger is None
        db.rollback()


def test_queue_contracts_match_recorded_original_legacy_oracle():
    import json
    from pathlib import Path
    import runpy
    evidence = Path(__file__).resolve().parents[2] / 'docs/design/evidence'
    oracle = runpy.run_path(str(evidence / 'deferred_queue_oracle.py'))
    expected = json.loads((evidence / 'deferred_queue_oracle.json').read_text())['legacy']['results']
    session = oracle['native_backend']()
    assert oracle['scenarios'](session) == expected
    session.close()


def test_postcommit_python_failure_keeps_commit_and_rolls_back_only_new_work():
    driver = Driver()
    session = Session(driver)

    def fail():
        session.execute(CompiledQuery('second'))
        raise ValueError('after commit')

    with pytest.raises(ValueError, match='after commit'):
        with session.transaction():
            session.execute(CompiledQuery('first'))
            session.defer_after_commit(fail)
    assert driver.persisted == ['first']
    assert driver.calls.count('commit') == driver.calls.count('rollback') == 1
    session.execute(CompiledQuery('recovered'))
    session.commit()
    assert driver.persisted == ['first', 'recovered']
    session.close()


def test_precommit_error_retains_original_exception_if_cleanup_fails():
    driver = Driver()
    session = Session(driver)
    original = ValueError('original')

    def fail():
        raise original

    driver.rollback_error = OSError('cleanup')
    with pytest.raises(ValueError) as caught:
        with session.transaction():
            session.execute(CompiledQuery('write'))
            session.defer_to_commit(fail)
    assert caught.value is original
    assert isinstance(caught.value.__cause__, OSError)
    assert session.outcome == 'unknown'
    driver.rollback_error = None
    session.rollback()
    session.close()
