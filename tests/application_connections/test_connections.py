from tests.unit_of_work import completed
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from asqueel.contracts import CompiledQuery, EnvironmentBinding, EnvironmentMismatchError, QueryResult
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.environment import SqlEnvironment
from asqueel.runtime import DatabaseClosedError, TransactionStateError
from asqueel.runtime import Database


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
        connection.clear()

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
    db = Database(driver=driver)
    with completed(db) as active:
        assert active is db
    db.commit()
    db.rollback()
    db.close()
    assert not driver.calls


def test_ambient_operations_share_connection_and_wait_for_commit():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('parent'))
    db.execute(CompiledQuery('child'))
    assert driver.calls == ['connect', 'parent', 'child']
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['parent', 'child']
    assert db.outcome == 'committed'
    db.execute(CompiledQuery('next'))
    db.close()
    assert driver.persisted == ['parent', 'child']
    assert db.outcome == 'rolled_back'
    assert driver.calls[-2:] == ['rollback', 'close']


def test_context_commits_atomically_or_rolls_back_on_python_error():
    driver = Driver()
    db = Database(driver=driver)
    with completed(db):
        db.execute(CompiledQuery('first'))
        db.execute(CompiledQuery('second'))
    assert driver.persisted == ['first', 'second']
    with pytest.raises(RuntimeError, match='hook'):
        with completed(db):
            db.execute(CompiledQuery('third'))
            raise RuntimeError('hook failed')
    assert driver.persisted == ['first', 'second']
    assert db.outcome == 'rolled_back'
    db.close()


def test_failed_ambient_connection_rolls_back_immediately_and_is_reusable():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('parent'))
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    assert db.outcome == 'rolled_back'
    assert driver.calls[-1] == 'rollback'
    assert driver.persisted == []
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    assert driver.calls.count('connect') == 1
    db.close()


@pytest.mark.parametrize('with_sql', [False, True])
def test_mark_failed_prevents_silent_context_success(with_sql):
    driver = Driver()
    db = Database(driver=driver)
    with pytest.raises(TransactionStateError, match='rollback-only'):
        with completed(db):
            if with_sql:
                db.execute(CompiledQuery('first'))
            db._mark_connection_failed(db._connection_state)
    assert driver.persisted == []
    assert driver.calls == (['connect', 'first', 'rollback'] if with_sql else [])
    with completed(db):
        db.execute(CompiledQuery('healthy'))
    assert driver.persisted == ['healthy']
    db.close()


def test_mark_failed_without_sql_requires_manual_rollback():
    driver = Driver()
    db = Database(driver=driver)
    db._mark_connection_failed(db._connection_state)
    with pytest.raises(TransactionStateError):
        db.commit()
    with pytest.raises(TransactionStateError):
        db.execute(CompiledQuery('must_not_run'))
    assert not driver.calls
    db.rollback()
    db.execute(CompiledQuery('ok'))
    db.commit()
    db.close()


def test_explicit_completion_accepts_pending_work_and_empty_repeated_commit():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('pending'))
    db.commit()
    db.commit()
    db.execute(CompiledQuery('next'))
    db.rollback()
    assert driver.persisted == ['pending']
    assert driver.calls.count('commit') == 1
    db.close()


def test_guards_run_before_connect_and_reject_stale_context():
    driver = Driver()
    environment = SqlEnvironment({'company': 1})
    db = Database(driver=driver, environment=environment)
    with pytest.raises(ValueError, match='profile'):
        db.execute(CompiledQuery('wrong', dialect='other'))
    query = CompiledQuery('select', environment=EnvironmentBinding(('company',), {'company': 1}))
    with environment.temp_env(company=2):
        with pytest.raises(EnvironmentMismatchError):
            db.execute(query)
    assert not driver.calls
    db.execute(query)
    db.rollback()
    db.close()


def test_connection_record_ownership_and_closed_database_state():
    driver = Driver()
    db = Database(driver=driver)
    state = db._connection_state
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(threading.get_ident).result() != threading.get_ident()
        for operation in (lambda: db._execute_on_connection(state, CompiledQuery('bad')),
                          lambda: db._commit_connection(state),
                          lambda: db._rollback_connection(state),
                          lambda: db._mark_connection_failed(state),
                          lambda: db._close_connection(state)):
            with pytest.raises(TransactionStateError, match='constructing thread'):
                executor.submit(operation).result()
    assert not driver.calls
    db.close()
    db.close()
    with pytest.raises(DatabaseClosedError):
        db.execute(CompiledQuery('closed'))


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_control_failure_preserves_original_and_attempts_close(operation):
    driver = Driver()
    error = OSError('control failed')
    setattr(driver, operation + '_error', error)
    driver.close_error = RuntimeError('close failed')
    db = Database(driver=driver)
    db.execute(CompiledQuery('pending'))
    with pytest.raises(OSError) as caught:
        getattr(db, operation)()
    assert caught.value is error
    assert db.outcome == 'unknown'
    assert driver.calls[-1] == 'close'
    db.close()


def test_close_marks_closed_even_when_rollback_cleanup_fails():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('pending'))
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(OSError):
        db.close()
    assert driver.calls[-1] == 'close'
    assert db.outcome == 'unknown'
    with pytest.raises(DatabaseClosedError):
        db.execute(CompiledQuery('closed'))


def test_driver_callback_cannot_reenter_connection_completion():
    driver = Driver()
    db = Database(driver=driver)
    def callback():
        for operation in (db.commit, db.rollback, db.close,
                          lambda: db.execute(CompiledQuery('recursive'))):
            with pytest.raises(TransactionStateError, match='executing'):
                operation()
    driver.callback = callback
    db.execute(CompiledQuery('outer'))
    db.commit()
    assert driver.persisted == ['outer']
    db.close()


def test_caught_driver_error_discards_prior_work_even_if_caller_commits():
    driver = Driver()
    db = Database(driver=driver)
    db.execute(CompiledQuery('before'))
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    db.commit()
    assert driver.persisted == []
    assert db.outcome == 'rolled_back'
    assert driver.calls[-1] == 'rollback'
    db.close()


def test_failed_connection_is_not_cached_and_can_be_retried():
    driver = Driver()
    original = driver.connect
    def fail(*args, **kwargs):
        raise OSError('connect failed')
    driver.connect = fail
    db = Database(driver=driver)
    with pytest.raises(OSError, match='connect failed'):
        db.execute(CompiledQuery('first'))
    assert db._connection_state['connection'] is None
    driver.connect = original
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    db.close()


def test_scope_does_not_clear_unknown_rollback_failure_on_unwind():
    driver = Driver()
    db = Database(driver=driver)
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    assert db.outcome == 'unknown'
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.execute(CompiledQuery('unsafe retry'))
    driver.rollback_error = None
    db.rollback()
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    db.close()
