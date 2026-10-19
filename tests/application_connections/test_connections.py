from tests.unit_of_work import completed
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from asqueel.contracts import CompiledQuery, QueryResult
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.environment import SqlEnvironment
from asqueel.runtime import TransactionStateError
from asqueel.runtime import Database


# Fake adapter loaded as legacy 'name:module': the database builds SqlDbAdapter(db).
FAKE = 'postgres:tests.application_connections.test_connections'


class SqlDbAdapter(PostgresAdapter):
    def __init__(self, dbroot):
        super().__init__(dbroot)
        self.calls = []
        self.executed_params = []
        self.persisted = []
        self.commit_error = None
        self.rollback_error = None
        self.close_error = None
        self.callback = None

    def connect(self, *args, **kwargs):
        self.calls.append('connect')
        return []

    def execute(self, connection, query):
        self.calls.append(query.sql)
        self.executed_params.append(dict(query.params))
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
    db = Database(implementation=FAKE)
    driver = db.adapter
    with completed(db) as active:
        assert active is db
    db.commit()
    db.rollback()
    db.closeConnection()
    assert not driver.calls


def test_ambient_operations_share_connection_and_wait_for_commit():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db.execute(CompiledQuery('parent'))
    db.execute(CompiledQuery('child'))
    assert driver.calls == ['connect', 'parent', 'child']
    assert driver.persisted == []
    db.commit()
    assert driver.persisted == ['parent', 'child']
    db.execute(CompiledQuery('next'))
    db.closeConnection()
    assert driver.persisted == ['parent', 'child']
    assert driver.calls[-2:] == ['rollback', 'close']


def test_context_commits_atomically_or_rolls_back_on_python_error():
    db = Database(implementation=FAKE)
    driver = db.adapter
    with completed(db):
        db.execute(CompiledQuery('first'))
        db.execute(CompiledQuery('second'))
    assert driver.persisted == ['first', 'second']
    with pytest.raises(RuntimeError, match='hook'):
        with completed(db):
            db.execute(CompiledQuery('third'))
            raise RuntimeError('hook failed')
    assert driver.persisted == ['first', 'second']
    db.closeConnection()


def test_failed_ambient_connection_rolls_back_immediately_and_is_reusable():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db.execute(CompiledQuery('parent'))
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    assert driver.calls[-1] == 'rollback'
    assert driver.persisted == []
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    assert driver.calls.count('connect') == 1
    db.closeConnection()


@pytest.mark.parametrize('with_sql', [False, True])
def test_mark_failed_prevents_silent_context_success(with_sql):
    db = Database(implementation=FAKE)
    driver = db.adapter
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
    db.closeConnection()


def test_mark_failed_without_sql_requires_manual_rollback():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db._mark_connection_failed(db._connection_state)
    with pytest.raises(TransactionStateError):
        db.commit()
    with pytest.raises(TransactionStateError):
        db.execute(CompiledQuery('must_not_run'))
    assert not driver.calls
    db.rollback()
    db.execute(CompiledQuery('ok'))
    db.commit()
    db.closeConnection()


def test_explicit_completion_accepts_pending_work_and_empty_repeated_commit():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db.execute(CompiledQuery('pending'))
    db.commit()
    db.commit()
    db.execute(CompiledQuery('next'))
    db.rollback()
    assert driver.persisted == ['pending']
    assert driver.calls.count('commit') == 1
    db.closeConnection()


def test_guards_run_before_connect_and_environment_is_read_at_execution():
    environment = SqlEnvironment({'company': 1})
    db = Database(implementation=FAKE, environment=environment)
    driver = db.adapter
    with pytest.raises(ValueError, match='profile'):
        db.execute(CompiledQuery('wrong', dialect='other'))
    assert not driver.calls
    query = CompiledQuery('select', {'env_company': 1}, environment_keys=('company',))
    with environment.temp_env(company=2):
        db.execute(query)
    assert driver.executed_params == [{'env_company': 2}]
    db.rollback()
    db.closeConnection()


def test_connection_record_ownership_and_repeated_close_connection():
    db = Database(implementation=FAKE)
    driver = db.adapter
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
    db.closeConnection()
    db.closeConnection()
    assert not driver.calls


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_control_failure_preserves_original_and_attempts_close(operation):
    db = Database(implementation=FAKE)
    driver = db.adapter
    error = OSError('control failed')
    setattr(driver, operation + '_error', error)
    driver.close_error = RuntimeError('close failed')
    db.execute(CompiledQuery('pending'))
    with pytest.raises(OSError) as caught:
        getattr(db, operation)()
    assert caught.value is error
    assert driver.calls[-1] == 'close'
    db.closeConnection()


def test_close_connection_closes_the_driver_connection_even_when_rollback_fails():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db.execute(CompiledQuery('pending'))
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(OSError):
        db.closeConnection()
    assert driver.calls[-1] == 'close'
    driver.rollback_error = None
    db.execute(CompiledQuery('reopened'))
    db.commit()
    assert driver.persisted == ['reopened']
    assert driver.calls.count('connect') == 2
    db.closeConnection()


def test_driver_callback_cannot_reenter_connection_completion():
    db = Database(implementation=FAKE)
    driver = db.adapter
    def callback():
        for operation in (db.commit, db.rollback, db.closeConnection,
                          lambda: db.execute(CompiledQuery('recursive'))):
            with pytest.raises(TransactionStateError, match='executing'):
                operation()
    driver.callback = callback
    db.execute(CompiledQuery('outer'))
    db.commit()
    assert driver.persisted == ['outer']
    db.closeConnection()


def test_caught_driver_error_discards_prior_work_even_if_caller_commits():
    db = Database(implementation=FAKE)
    driver = db.adapter
    db.execute(CompiledQuery('before'))
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    db.commit()
    assert driver.persisted == []
    assert driver.calls[-1] == 'rollback'
    db.closeConnection()


def test_failed_connection_is_not_cached_and_can_be_retried():
    db = Database(implementation=FAKE)
    driver = db.adapter
    original = driver.connect
    def fail(*args, **kwargs):
        raise OSError('connect failed')
    driver.connect = fail
    with pytest.raises(OSError, match='connect failed'):
        db.execute(CompiledQuery('first'))
    assert db._connection_state['connection'] is None
    driver.connect = original
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    db.closeConnection()


def test_scope_does_not_clear_unknown_rollback_failure_on_unwind():
    db = Database(implementation=FAKE)
    driver = db.adapter
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(LookupError):
        db.execute(CompiledQuery('fail'))
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.execute(CompiledQuery('unsafe retry'))
    driver.rollback_error = None
    db.rollback()
    db.execute(CompiledQuery('recovered'))
    db.commit()
    assert driver.persisted == ['recovered']
    db.closeConnection()
