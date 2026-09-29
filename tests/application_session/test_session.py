from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from genro_sql.contracts import CompiledQuery, EnvironmentBinding, EnvironmentMismatchError, QueryResult
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.environment import SqlEnvironment
from genro_sql.runtime import DatabaseClosedError, TransactionStateError
from genro_sql.session import Session


class Driver:
    dialect = 'postgresql'
    binding = 'psycopg_named'

    def __init__(self):
        self.calls = []
        self.persisted = []
        self.commit_error = None
        self.rollback_error = None
        self.close_error = None
        self.callback = None

    def prepare(self, statement):
        return PsycopgDriver().prepare(statement)

    def validate(self, query):
        PsycopgDriver().validate(query)

    def connect(self, *args, **kwargs):
        self.calls.append('connect')
        return []

    def execute(self, connection, query):
        self.calls.append(query.sql)
        if self.callback:
            self.callback()
        if query.sql == 'fail':
            raise LookupError('statement failed')
        connection.append(query.sql)
        return QueryResult([{'sql': query.sql}], 1)

    def commit(self, connection):
        self.calls.append('commit')
        if self.commit_error:
            raise self.commit_error
        self.persisted.extend(connection)

    def rollback(self, connection):
        self.calls.append('rollback')
        if self.rollback_error:
            raise self.rollback_error
        connection.clear()

    def close(self, connection):
        self.calls.append('close')
        if self.close_error:
            raise self.close_error


def test_creation_and_empty_context_have_no_io():
    driver = Driver()
    session = Session(driver)
    with session.transaction() as active:
        assert active is session
    session.commit()
    session.rollback()
    session.close()
    assert not driver.calls


def test_ambient_operations_share_connection_and_wait_for_commit():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('parent'))
    session.execute(CompiledQuery('child'))
    assert driver.calls == ['connect', 'parent', 'child']
    assert driver.persisted == []
    session.commit()
    assert driver.persisted == ['parent', 'child']
    assert session.outcome == 'committed'
    session.execute(CompiledQuery('next'))
    session.close()
    assert driver.persisted == ['parent', 'child']
    assert session.outcome == 'rolled_back'
    assert driver.calls[-2:] == ['rollback', 'close']


def test_context_commits_atomically_or_rolls_back_on_python_error():
    driver = Driver()
    session = Session(driver)
    with session.transaction():
        session.execute(CompiledQuery('first'))
        session.execute(CompiledQuery('second'))
    assert driver.persisted == ['first', 'second']
    with pytest.raises(RuntimeError, match='hook'):
        with session.transaction():
            session.execute(CompiledQuery('third'))
            raise RuntimeError('hook failed')
    assert driver.persisted == ['first', 'second']
    assert session.outcome == 'rolled_back'
    session.close()


def test_failed_ambient_session_requires_explicit_rollback():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('parent'))
    with pytest.raises(LookupError):
        session.execute(CompiledQuery('fail'))
    with pytest.raises(TransactionStateError, match='rollback-only'):
        session.commit()
    with pytest.raises(TransactionStateError, match='rollback-only'):
        session.execute(CompiledQuery('later'))
    assert driver.persisted == []
    session.rollback()
    session.execute(CompiledQuery('recovered'))
    session.commit()
    assert driver.persisted == ['recovered']
    session.close()


@pytest.mark.parametrize('with_sql', [False, True])
def test_mark_failed_prevents_silent_context_success(with_sql):
    driver = Driver()
    session = Session(driver)
    with pytest.raises(TransactionStateError, match='rolled back'):
        with session.transaction():
            if with_sql:
                session.execute(CompiledQuery('first'))
            session.mark_failed()
    assert driver.persisted == []
    assert driver.calls == (['connect', 'first', 'rollback', 'close'] if with_sql else [])
    with session.transaction():
        session.execute(CompiledQuery('healthy'))
    assert driver.persisted == ['healthy']
    session.close()


def test_mark_failed_without_sql_requires_manual_rollback():
    driver = Driver()
    session = Session(driver)
    session.mark_failed()
    with pytest.raises(TransactionStateError):
        session.commit()
    with pytest.raises(TransactionStateError):
        session.execute(CompiledQuery('must_not_run'))
    assert not driver.calls
    session.rollback()
    session.execute(CompiledQuery('ok'))
    session.commit()
    session.close()


def test_context_rejects_nested_adoption_and_manual_completion():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('pending'))
    with pytest.raises(TransactionStateError, match='pending'):
        with session.transaction():
            pass
    session.rollback()
    with session.transaction():
        with pytest.raises(TransactionStateError, match='Nested'):
            with session.transaction():
                pass
        for operation in (session.commit, session.rollback, session.close):
            with pytest.raises(TransactionStateError, match='context owns'):
                operation()
        session.execute(CompiledQuery('ok'))
    assert driver.persisted == ['ok']
    session.close()


def test_guards_run_before_connect_and_reject_stale_context():
    driver = Driver()
    environment = SqlEnvironment({'company': 1})
    session = Session(driver, environment=environment)
    with pytest.raises(ValueError, match='profile'):
        session.execute(CompiledQuery('wrong', dialect='other'))
    query = CompiledQuery('select', environment=EnvironmentBinding(('company',), {'company': 1}))
    with environment.temp_env(company=2):
        with pytest.raises(EnvironmentMismatchError):
            session.execute(query)
    assert not driver.calls
    session.execute(query)
    session.rollback()
    session.close()


def test_thread_ownership_and_closed_state():
    driver = Driver()
    session = Session(driver)
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(threading.get_ident).result() != threading.get_ident()
        for operation in (lambda: session.execute(CompiledQuery('bad')), session.commit,
                          session.rollback, session.mark_failed, session.close):
            with pytest.raises(TransactionStateError, match='constructing thread'):
                executor.submit(operation).result()
    assert not driver.calls
    session.close()
    session.close()
    with pytest.raises(DatabaseClosedError):
        session.execute(CompiledQuery('closed'))


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_control_failure_preserves_original_and_attempts_close(operation):
    driver = Driver()
    error = OSError('control failed')
    setattr(driver, operation + '_error', error)
    driver.close_error = RuntimeError('close failed')
    session = Session(driver)
    session.execute(CompiledQuery('pending'))
    with pytest.raises(OSError) as caught:
        getattr(session, operation)()
    assert caught.value is error
    assert session.outcome == 'unknown'
    assert driver.calls[-1] == 'close'
    session.close()


def test_close_marks_closed_even_when_rollback_cleanup_fails():
    driver = Driver()
    session = Session(driver)
    session.execute(CompiledQuery('pending'))
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(OSError):
        session.close()
    assert driver.calls[-1] == 'close'
    assert session.outcome == 'unknown'
    with pytest.raises(DatabaseClosedError):
        session.execute(CompiledQuery('closed'))


def test_driver_callback_cannot_reenter_session_completion():
    driver = Driver()
    session = Session(driver)
    def callback():
        for operation in (session.commit, session.rollback, session.close,
                          lambda: session.execute(CompiledQuery('recursive'))):
            with pytest.raises(TransactionStateError, match='executing'):
                operation()
    driver.callback = callback
    session.execute(CompiledQuery('outer'))
    session.commit()
    assert driver.persisted == ['outer']
    session.close()


def test_caught_driver_error_cannot_commit_context_as_success():
    driver = Driver()
    session = Session(driver)
    with pytest.raises(TransactionStateError, match='rolled back'):
        with session.transaction():
            session.execute(CompiledQuery('before'))
            with pytest.raises(LookupError):
                session.execute(CompiledQuery('fail'))
    assert driver.persisted == []
    assert session.outcome == 'rolled_back'
    assert driver.calls[-2:] == ['rollback', 'close']
    session.close()


def test_failed_connection_requires_rollback_but_never_retains_active_runtime_transaction():
    driver = Driver()
    original = driver.connect
    def fail(*args, **kwargs):
        raise OSError('connect failed')
    driver.connect = fail
    session = Session(driver)
    with pytest.raises(OSError, match='connect failed'):
        session.execute(CompiledQuery('first'))
    with pytest.raises(TransactionStateError, match='rollback-only'):
        session.execute(CompiledQuery('second'))
    session.rollback()
    driver.connect = original
    session.execute(CompiledQuery('recovered'))
    session.commit()
    assert driver.persisted == ['recovered']
    session.close()
