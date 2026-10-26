"""Commit lifecycle contracts, including failures hidden inside callbacks."""
import textwrap

from tests.unit_of_work import completed
import pytest

from asqueel import CompiledQuery, DeferredCommitError, TransactionStateError, AsqueelDb
from tests.unit_of_work import empty_database
from tests.application_config.test_application import Recipe, layout_recipe
from tests.application_connections.test_connections import FAKE

ITEM = '''
import pytest

from asqueel import CompiledQuery, TransactionStateError


class Table:
    def config_db(self, pkg):
        pkg.tables().table('item', pkey='id').columns().column('id', dtype='I')
'''


def database(folder, item_methods):
    """``Recipe`` whose ``app.item`` has the methods ``item_methods``."""
    item = ITEM + textwrap.indent(textwrap.dedent(item_methods), '    ')
    return AsqueelDb(layout_recipe(folder, item)).session()


def test_hooks_can_register_both_queues_and_deferred_errors(tmp_path):
    db = database(tmp_path / 'app', '''
        events = []

        def trigger_onInserting(self, record):
            commits = self.db.adapter.calls.count
            self.db.deferToCommit(lambda: self.events.append(('before', commits('commit'))))
            self.db.deferAfterCommit(lambda: self.events.append(('after', commits('commit'))))
            if record['id'] == 2:
                self.db.deferredRaise(ValueError('invalid record'))
    ''')
    events = db.table('app.item').events
    try:
        db.table('app.item').insert({'id': 1})
        assert events == []
        db.commit()
        assert events == [('before', 0), ('after', 1)]
        db.table('app.item').insert({'id': 2})
        with pytest.raises(DeferredCommitError, match='invalid record'):
            db.commit()
        db.rollback()
        assert events[-1] == ('before', 1)
        assert db.adapter.calls.count('commit') == 1
    finally:
        db.closeConnection()


def test_precommit_failure_rolls_back_atomic_scope_and_clears_callbacks():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
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
    db.closeConnection()


@pytest.mark.parametrize('queue', ['before', 'after'])
def test_caught_sql_error_cannot_continue_commit_or_callbacks(queue):
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
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
    db.closeConnection()


def test_caught_domain_failure_in_callback_cannot_be_committed():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
    db.execute(CompiledQuery('write'))
    db.deferToCommit(lambda: db._mark_connection_failed(db._connection_state))
    with pytest.raises(TransactionStateError):
        db.commit()
    assert driver.persisted == []
    db.rollback()
    db.closeConnection()


def test_commit_selects_current_name_and_callbacks_restore_environment():
    db = AsqueelDb(Recipe).session()
    a = db.session('A')
    b = db.session('B')
    try:
        events = []
        with a.tempEnv(onCommittingStep=False):
            a.execute(CompiledQuery('A'))
            a.deferToCommit(lambda: events.append((a.currentConnectionName, a.currentEnv['onCommittingStep'])))
            a.deferAfterCommit(lambda: events.append((a.currentConnectionName, a.currentEnv['onCommittingStep'])))
            b.commit()
            db.commit()
            assert events == []
            a.commit()
            assert a.currentConnectionName == 'A'
            assert a.currentEnv['onCommittingStep'] is False
        assert events == [('A', True), ('A', True)]
    finally:
        a.close()
        b.close()
        db.closeConnection()


def test_named_queues_and_pending_exceptions_are_independent():
    db = AsqueelDb(Recipe).session()
    other = db.session('other')
    try:
        events = []
        db.execute(CompiledQuery('main'))
        db.deferToCommit(lambda: events.append('main'))
        other.execute(CompiledQuery('other'))
        other.deferToCommit(lambda: events.append('other'))
        other.deferAfterCommit(lambda: events.append('other after'))
        other.commit()
        assert events == ['other', 'other after']
        assert other.adapter.persisted == ['other']
        # Legacy keeps one global _pendingExceptions; here, as the deferred
        # queues, they belong to their session.
        db.deferredRaise(ValueError('main error'))
        other.execute(CompiledQuery('other again'))
        other.commit()
        assert other.adapter.persisted == ['other', 'other again']
        with pytest.raises(DeferredCommitError, match='main error'):
            db.commit()
        db.rollback()
        assert events == ['other', 'other after', 'main']
        assert db.adapter.persisted == []
        assert other.adapter.persisted == ['other', 'other again']
    finally:
        other.close()
        db.closeConnection()


@pytest.mark.parametrize('completion', ['rollback', 'closeConnection'])
def test_discard_clears_queues_even_without_sql(completion):
    db = empty_database(implementation=FAKE).session()
    events = []
    db.deferToCommit(lambda: events.append('before'))
    db.deferAfterCommit(lambda: events.append('after'))
    db.deferredRaise(ValueError('discard'))
    getattr(db, completion)()
    db.execute(CompiledQuery('new'))
    db.commit()
    assert events == []
    db.closeConnection()


def test_unknown_commit_never_dispatches_after_and_discards_queue():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
    events = []
    db.execute(CompiledQuery('write'))
    db.deferAfterCommit(lambda: events.append('after'))
    driver.commit_error = OSError('unknown commit')
    with pytest.raises(OSError):
        db.commit()
    assert events == []
    driver.commit_error = None
    db.rollback()
    db.execute(CompiledQuery('next'))
    db.commit()
    assert events == []
    db.closeConnection()


def test_after_callback_can_start_next_transaction_as_in_legacy():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
    db.execute(CompiledQuery('first'))
    db.deferAfterCommit(lambda: db.execute(CompiledQuery('second')))
    db.commit()
    assert driver.persisted == ['first', 'second']
    assert driver.calls.count('commit') == 2
    db.closeConnection()


@pytest.mark.parametrize('action', ['commit', 'rollback', 'closeConnection'])
def test_callback_cannot_reenter_transaction_completion(action):
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
    db.execute(CompiledQuery('write'))
    db.deferToCommit(getattr(db, action))
    with pytest.raises(TransactionStateError):
        db.commit()
    assert not driver.persisted
    db.rollback()
    db.closeConnection()


def test_stack_tracks_nested_writes_and_restores_after_exception(tmp_path):
    db = database(tmp_path / 'app', '''
        events = []

        def trigger_onInserting(self, record):
            current = self.currentTrigger
            self.events.append((current.event, current.table,
                                current.parent.record['id'] if current.parent else None))
            if record['id'] == 1:
                self.insert({'id': 2})
                assert self.currentTrigger is current
            elif record['id'] == 3:
                raise ValueError('hook')
    ''')
    events = db.table('app.item').events
    try:
        db.table('app.item').insert({'id': 1})
        assert db.currentTrigger is None
        assert events == [('insert', 'app.item', None), ('insert', 'app.item', 1)]
        db.commit()
        with pytest.raises(ValueError):
            db.table('app.item').insert({'id': 3})
        assert db.currentTrigger is None
        db.rollback()
    finally:
        db.closeConnection()


def test_queue_contracts_match_recorded_original_legacy_oracle():
    import json
    from pathlib import Path
    import runpy
    evidence = Path(__file__).resolve().parents[2] / 'docs/design/evidence'
    oracle = runpy.run_path(str(evidence / 'deferred_queue_oracle.py'))
    expected = json.loads((evidence / 'deferred_queue_oracle.json').read_text())['legacy']['results']
    db = oracle['native_backend']()
    assert oracle['scenarios'](db) == expected
    db.closeConnection()


def test_postcommit_python_failure_keeps_commit_and_rolls_back_only_new_work():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter

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
    db.closeConnection()


def test_precommit_error_retains_original_exception_if_cleanup_fails():
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
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
    driver.rollback_error = None
    db.rollback()
    db.closeConnection()


@pytest.mark.parametrize('queue', ['before', 'after'])
def test_callback_can_handle_external_failure_and_continue_queue(queue):
    db = empty_database(implementation=FAKE).session()
    driver = db.adapter
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
        db.closeConnection()


def test_postcommit_error_leaves_unreached_callbacks_until_application_cleanup():
    db = empty_database(implementation=FAKE).session()
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
        assert db.adapter.persisted == ['saved', 'next']
    finally:
        db.closeConnection()


@pytest.mark.parametrize('action', ['commit', 'rollback'])
def test_trigger_finishes_another_named_connection_but_not_its_own(action, tmp_path):
    db = database(tmp_path / 'app', '''
        action = None

        def trigger_onInserting(self, record):
            with pytest.raises(TransactionStateError, match='in progress'):
                getattr(self.db, self.action)()
            system = self.db.session('system')
            system.execute(CompiledQuery('log'))
            getattr(system, self.action)()
    ''')
    db.table('app.item').action = action
    try:
        db.table('app.item').insert({'id': 1})
        assert db.session('system').adapter.persisted == (['log'] if action == 'commit' else [])
        assert db.adapter.persisted == []
        with pytest.raises(TransactionStateError, match='inside a table write'):
            with db._write_operation():
                db.closeConnection()
        db.rollback()
    finally:
        db.closeConnection()


def test_deferred_blocks_run_in_lowercase_label_order():
    db = empty_database(implementation=FAKE).session()
    events = []
    for block in ('b', 'C', 'A', 'a'):
        db.deferToCommit(events.append, block, _deferredBlock=block)
    db.execute(CompiledQuery('work'))
    db.commit()
    assert events == ['A', 'a', 'b', 'C']
    db.closeConnection()
