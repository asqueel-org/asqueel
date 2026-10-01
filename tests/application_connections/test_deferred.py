"""Commit lifecycle contracts, including failures hidden inside callbacks."""
from tests.unit_of_work import completed
import pytest

from asqueel import CompiledQuery, DeferredCommitError, SqlTable, TransactionStateError, build_database
from asqueel.runtime import Database
from tests.application_config.test_application import Recipe
from tests.application_connections.test_connections import Driver


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
    db = Database(driver=driver)
    events = []

    def fail():
        raise ValueError('pre-commit')

    with pytest.raises(ValueError, match='pre-commit'):
        with completed(db):
            db.execute(CompiledQuery('write'))
            db.deferToCommit(fail)
            db.deferAfterCommit(lambda: events.append('after'))
    assert driver.calls[-1] == 'rollback'
    assert not driver.persisted
    db.execute(CompiledQuery('recovery'))
    db.commit()
    assert driver.persisted == ['recovery']
    assert events == []
    db.close()


@pytest.mark.parametrize('queue', ['before', 'after'])
def test_caught_sql_error_cannot_continue_commit_or_callbacks(queue):
    driver = Driver()
    db = Database(driver=driver)
    events = []
    db.execute(CompiledQuery('write'))

    def fail():
        try:
            db.execute(CompiledQuery('fail'))
        except LookupError:
            pass
        # Even a fresh registration must not resurrect the aborted commit.
        db.deferAfterCommit(lambda: events.append('resurrected'))

    register = db.deferToCommit if queue == 'before' else db.deferAfterCommit
    register(fail)
    register(lambda: events.append('later'))
    with pytest.raises(TransactionStateError):
        db.commit()
    assert driver.calls.count('commit') == (queue == 'after')
    assert driver.persisted == (['write'] if queue == 'after' else [])
    assert events == []
    db.rollback()
    db.execute(CompiledQuery('recovery'))
    db.commit()
    assert events == []
    db.close()


def test_caught_domain_failure_in_callback_cannot_be_committed():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('write'))
    db.deferToCommit(lambda: db._mark_connection_failed(db._connection_state))
    with pytest.raises(TransactionStateError):
        db.commit()
    assert driver.persisted == []
    db.rollback()
    db.close()


def test_commit_selects_current_name_and_callbacks_restore_environment():
    with database() as db:
        events = []
        with db.tempEnv(connectionName='A', onCommittingStep=False):
            db.execute(CompiledQuery('A'))
            db.deferToCommit(lambda: events.append((db.currentConnectionName, db.currentEnv['onCommittingStep'])))
            db.deferAfterCommit(lambda: events.append((db.currentConnectionName, db.currentEnv['onCommittingStep'])))
            with db.tempEnv(connectionName='B'):
                db.commit()
                assert events == []
            db.commit()
            assert db.currentConnectionName == 'A'
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
    db = Database(driver=Driver())
    events = []
    db.deferToCommit(lambda: events.append('before'))
    db.deferAfterCommit(lambda: events.append('after'))
    db.deferredRaise(ValueError('discard'))
    getattr(db, completion)()
    if completion == 'rollback':
        db.execute(CompiledQuery('new'))
        db.commit()
    assert events == []
    db.close()


def test_unknown_commit_never_dispatches_after_and_discards_queue():
    driver = Driver()
    db = Database(driver=driver)
    events = []
    db.execute(CompiledQuery('write'))
    db.deferAfterCommit(lambda: events.append('after'))
    driver.commit_error = OSError('unknown commit')
    with pytest.raises(OSError):
        db.commit()
    assert db.outcome == 'unknown'
    assert events == []
    driver.commit_error = None
    db.rollback()
    db.execute(CompiledQuery('next'))
    db.commit()
    assert events == []
    db.close()


def test_after_callback_can_start_next_transaction_as_in_legacy():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('first'))
    db.deferAfterCommit(lambda: db.execute(CompiledQuery('second')))
    db.commit()
    assert driver.persisted == ['first', 'second']
    assert driver.calls.count('commit') == 2
    db.close()


@pytest.mark.parametrize('action', ['commit', 'rollback', 'close'])
def test_callback_cannot_reenter_transaction_completion(action):
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('write'))
    db.deferToCommit(getattr(db, action))
    with pytest.raises(TransactionStateError):
        db.commit()
    assert not driver.persisted
    db.rollback()
    db.close()


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
    db = oracle['native_backend']()
    assert oracle['scenarios'](db) == expected
    db.close()


def test_postcommit_python_failure_keeps_commit_and_rolls_back_only_new_work():
    driver = Driver()
    db = Database(driver=driver)

    def fail():
        db.execute(CompiledQuery('second'))
        raise ValueError('after commit')

    with pytest.raises(ValueError, match='after commit'):
        with completed(db):
            db.execute(CompiledQuery('first'))
            db.deferAfterCommit(fail)
    assert driver.persisted == ['first']
    assert driver.calls.count('commit') == driver.calls.count('rollback') == 1
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['first', 'recovered']
    db.close()


def test_precommit_error_retains_original_exception_if_cleanup_fails():
    driver = Driver()
    db = Database(driver=driver)
    original = ValueError('original')

    def fail():
        raise original

    driver.rollback_error = OSError('cleanup')
    with pytest.raises(ValueError) as caught:
        with completed(db):
            db.execute(CompiledQuery('write'))
            db.deferToCommit(fail)
    assert caught.value is original
    assert isinstance(caught.value.__cause__, OSError)
    assert db.outcome == 'unknown'
    driver.rollback_error = None
    db.rollback()
    db.close()


@pytest.mark.parametrize('queue', ['before', 'after'])
def test_callback_can_handle_external_failure_and_continue_queue(queue):
    driver = Driver()
    db = Database(driver=driver)
    events = []

    def handled():
        try:
            raise OSError('external service unavailable')
        except OSError:
            events.append('handled')

    try:
        db.execute(CompiledQuery('write'))
        register = db.deferToCommit if queue == 'before' else db.deferAfterCommit
        register(handled)
        register(lambda: events.append('next'))
        db.commit()
        assert events == ['handled', 'next']
        assert driver.persisted == ['write']
        db.commit()
        assert events == ['handled', 'next']
    finally:
        db.close()


def test_postcommit_error_leaves_unreached_callbacks_until_application_cleanup():
    db = Database(driver=Driver())
    events = []
    original = ValueError('notification failed')

    def notify():
        events.append('notify')
        raise original

    try:
        db.execute(CompiledQuery('saved'))
        db.deferAfterCommit(notify)
        db.deferAfterCommit(lambda: events.append('log'))
        with pytest.raises(ValueError) as raised:
            db.commit()
        assert raised.value is original
        assert events == ['notify']
        db.commit()  # No new work: no automatic callback retry.
        assert events == ['notify']
        # The application deliberately continues in the same request/context.
        db.execute(CompiledQuery('next'))
        db.commit()
        assert events == ['notify', 'log']
        assert db.driver.persisted == ['saved', 'next']
    finally:
        db.close()
