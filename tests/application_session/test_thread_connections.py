"""One DB graph, independent thread environments and named connections."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from asqueel import AsqueelDb, TransactionStateError
from asqueel.contracts import CompiledQuery
from asqueel.environment import SqlEnvironment
from tests.application_config.test_application import Recipe
from tests.application_session.test_session import Driver


def test_simultaneous_threads_isolate_names_environment_hooks_and_completion():
    driver = Driver()
    db = AsqueelDb(Recipe, driver=driver, environment=SqlEnvironment({'options': []}))
    barrier = Barrier(2)
    callbacks = []

    def worker(name, fail):
        db.currentEnv['options'].append(name)
        db.updateEnv(user=name)
        connections = []
        try:
            for connection_name in ('_main_connection', 'other'):
                with db.tempEnv(connectionName=connection_name):
                    connection = db._session
                    connections.append(connection)
                    assert connection is db._session
                    db.execute(CompiledQuery(name + connection_name))
                    db.deferToCommit(lambda: callbacks.append(db.currentEnv['user']))
                    with db._trigger_operation('insert', db.table('app.item')) as trigger:
                        with db._write_operation():
                            barrier.wait(timeout=10)
                            assert db.currentTrigger is trigger
                            assert trigger.level == 0
                            assert db._write_depth == 1
                            assert db.currentEnv['options'] == [name]
                            barrier.wait(timeout=10)
                    if fail:
                        db.rollback()
                    else:
                        db.commit()
            return connections
        finally:
            db.closeConnection()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, 'alice', False)
        second = pool.submit(worker, 'bob', True)
        handles = first.result() + second.result()
    assert len({id(handle) for handle in handles}) == 4
    assert callbacks == ['alice', 'alice']
    assert driver.persisted == ['alice_main_connection', 'aliceother']
    assert driver.calls.count('connect') == driver.calls.count('close') == 4
    assert db.currentEnv == {'options': []}
    assert db.currentTrigger is None
    db.close()


def test_named_environment_changes_selection_without_completion():
    driver = Driver()
    db = AsqueelDb(Recipe, driver=driver)
    assert not hasattr(db, 'transaction')
    assert not hasattr(db, 'connection')
    db.execute(CompiledQuery('main'))
    with db.tempEnv(connectionName='other'):
        db.execute(CompiledQuery('other'))
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['main']
    with db.tempEnv(connectionName='other'):
        db.rollback()
    db.close()


def test_internal_connection_rejects_cross_thread_use():
    db = AsqueelDb(Recipe, driver=Driver())
    session = db._session
    with ThreadPoolExecutor(max_workers=1) as pool:
        for operation in (session.commit, session.rollback):
            with pytest.raises(TransactionStateError, match='constructing thread'):
                pool.submit(operation).result()
    db.close()


def test_explicit_commit_preserves_deferred_hook_and_pending_work():
    driver = Driver()
    db = AsqueelDb(Recipe, driver=driver)
    db.execute(CompiledQuery('before'))
    db.deferToCommit(lambda: db.execute(CompiledQuery('hook')))
    db.execute(CompiledQuery('inside'))
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['before', 'inside', 'hook']
    assert driver.calls.count('connect') == 1
    db.close()


def test_new_thread_does_not_inherit_closed_state_or_environment():
    db = AsqueelDb(Recipe, driver=Driver())
    def worker():
        assert db.currentEnv == {}
        db.updateEnv(user='previous')
        db.close()
    for _ in range(2):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(worker).result()
    assert db.currentEnv == {}
    db.close()
