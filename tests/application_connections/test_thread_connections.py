"""One DB graph, independent call environments and named sessions."""
from concurrent.futures import ThreadPoolExecutor
import contextvars
from threading import Barrier

from asqueel import AsqueelDb
from asqueel.contracts import CompiledQuery
from tests.application_config.test_application import Recipe


def test_simultaneous_calls_isolate_names_environment_hooks_and_completion():
    shared = AsqueelDb(Recipe, environment={'options': []})
    barrier = Barrier(2)
    callbacks = []
    sessions = []

    def worker(name, fail):
        connections = []
        for connection_name in (None, 'other'):
            db = shared.session(connection_name, user=name)
            sessions.append(db)
            try:
                db.currentEnv['options'].append(name)
                connection = db._connection_state
                connections.append(connection)
                assert connection is db._connection_state
                db.execute(CompiledQuery(name + db.currentConnectionName))
                db.deferToCommit(lambda db=db: callbacks.append(db.currentEnv['user']))
                with db._trigger_operation('insert', db.table('app.item')) as trigger:
                    with db._write_operation():
                        barrier.wait(timeout=10)
                        assert db.currentTrigger is trigger
                        assert db._write_depth == 1
                        assert db.currentEnv['options'] == [name]
                        barrier.wait(timeout=10)
                if fail:
                    db.rollback()
                else:
                    db.commit()
            finally:
                db.close()
        return connections

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(contextvars.Context().run, worker, 'alice', False)
        second = pool.submit(contextvars.Context().run, worker, 'bob', True)
        handles = first.result() + second.result()
    assert len({id(handle) for handle in handles}) == 4
    assert len({id(session) for session in sessions}) == 4
    assert callbacks == ['alice', 'alice']
    assert sorted(item for session in sessions for item in session.adapter.persisted) == [
        'alice_main_connection', 'aliceother']
    assert sum(session.adapter.calls.count('connect') for session in sessions) == 4
    assert sum(session.adapter.calls.count('close') for session in sessions) == 4
    assert shared.currentEnv == {'options': []}
    assert shared.currentTrigger is None
    shared.close()


def test_named_session_changes_selection_without_completion():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    assert not hasattr(db, 'transaction')
    assert not hasattr(db, 'connection')
    db.execute(CompiledQuery('main'))
    other = db.session('other')
    other.execute(CompiledQuery('other'))
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['main']
    assert other.adapter.persisted == []
    other.rollback()
    other.close()
    db.closeConnection()


def test_internal_connection_is_usable_from_another_thread_of_the_call():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    db.execute(CompiledQuery('pending'))
    state = db._connection_state
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(db._rollback_connection, state).result()
        pool.submit(db._commit_connection, state).result()
    assert driver.calls == ['connect', 'pending', 'rollback']
    assert driver.persisted == []
    db.closeConnection()


def test_explicit_commit_preserves_deferred_hook_and_pending_work():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    db.execute(CompiledQuery('before'))
    db.deferToCommit(lambda: db.execute(CompiledQuery('hook')))
    db.execute(CompiledQuery('inside'))
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['before', 'inside', 'hook']
    assert driver.calls.count('connect') == 1
    db.closeConnection()


def test_new_call_does_not_inherit_environment():
    shared = AsqueelDb(Recipe)

    def call():
        db = shared.session()
        assert db.currentEnv == {}
        db.updateEnv(user='previous')
        db.close()
    for _ in range(2):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(contextvars.Context().run, call).result()
    assert shared.currentEnv == {}
    shared.close()
