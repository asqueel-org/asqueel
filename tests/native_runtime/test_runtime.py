import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from asqueel.contracts import CompiledQuery, ResultColumn
from asqueel.runtime import DatabaseClosedError, PostgresDatabase, TransactionStateError


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls
        self.description = [SimpleNamespace(name='value')]
        self.rowcount = 1

    def record(self, name):
        self.calls.append((name, threading.get_ident()))

    def cursor(self, **kwargs):
        self.record('cursor')
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.record('cursor_close')

    def execute(self, sql, params):
        self.record(sql)
        if sql == 'error':
            raise ValueError('statement failed')

    def fetchall(self):
        self.record('fetch')
        return [(42,)]

    def commit(self):
        self.record('commit')

    def rollback(self):
        self.record('rollback')

    def close(self):
        self.record('close')


@pytest.fixture
def fake(monkeypatch):
    import psycopg
    calls = []

    def connect(*args, **kwargs):
        connection = FakeConnection(calls)
        connection.record('connect')
        return connection

    monkeypatch.setattr(psycopg, 'connect', connect)
    return calls


def test_shared_execute_retains_connection_until_explicit_completion(fake):
    from asqueel.application import SqlDatabase
    from asqueel.runtime import Database
    assert SqlDatabase.execute is Database.execute
    db = PostgresDatabase()
    assert not hasattr(db, 'transaction')
    assert not hasattr(db, 'connection')
    result = db.execute(CompiledQuery('select'))
    assert result.rows == [{'value': 42}]
    assert not any(name == 'commit' for name, _ in fake)
    db.commit()
    db.execute(CompiledQuery('second'))
    db.rollback()
    db.close()
    names = [name for name, _ in fake]
    assert names.count('connect') == names.count('commit') == names.count('rollback') == names.count('close') == 1
    assert {thread for _, thread in fake} == {threading.get_ident()}


def test_sql_error_rolls_back_and_explicit_retry_reuses_connection(fake):
    with PostgresDatabase() as db:
        db.execute(CompiledQuery('first'))
        with pytest.raises(ValueError, match='statement failed'):
            db.execute(CompiledQuery('error'))
        assert db.outcome == 'rolled_back'
        db.execute(CompiledQuery('recovered'))
        db.commit()
    assert [name for name, _ in fake].count('connect') == 1


def test_close_discards_pending_work_and_closes_only_current_thread(fake):
    db = PostgresDatabase()
    db.execute(CompiledQuery('select'))
    def worker():
        try:
            db.execute(CompiledQuery('worker'))
            db.commit()
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()
    db.execute(CompiledQuery('still open'))
    db.close()
    assert [name for name, _ in fake][-2:] == ['rollback', 'close']
    with pytest.raises(DatabaseClosedError):
        db.execute(CompiledQuery('closed'))


def test_failed_open_allows_another_attempt(fake, monkeypatch):
    import psycopg
    original = psycopg.connect
    with PostgresDatabase() as db:
        monkeypatch.setattr(psycopg, 'connect', lambda *a, **kw: (_ for _ in ()).throw(OSError('open failed')))
        with pytest.raises(OSError, match='open failed'):
            db.execute(CompiledQuery('select'))
        monkeypatch.setattr(psycopg, 'connect', original)
        assert db.execute(CompiledQuery('select')).rowcount == 1
        db.commit()


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_completion_failure_discards_connection_and_marks_unknown(fake, monkeypatch, operation):
    failure = OSError(f'{operation} failed')
    def fail(self):
        raise failure
    monkeypatch.setattr(FakeConnection, operation, fail)
    with PostgresDatabase() as db:
        db.execute(CompiledQuery('select'))
        with pytest.raises(OSError) as caught:
            getattr(db, operation)()
        assert caught.value is failure
        assert db.outcome == 'unknown'
        assert fake[-1][0] == 'close'


def test_commit_error_is_not_masked_by_cleanup_failure(fake, monkeypatch):
    failure = OSError('commit failed')
    def fail_commit(self):
        raise failure
    def fail_close(self):
        raise RuntimeError('close failed')
    monkeypatch.setattr(FakeConnection, 'commit', fail_commit)
    monkeypatch.setattr(FakeConnection, 'close', fail_close)
    with PostgresDatabase() as db:
        db.execute(CompiledQuery('select'))
        with pytest.raises(OSError) as caught:
            db.commit()
        assert caught.value is failure
        assert db.outcome == 'unknown'
        assert 'cleanup' in failure.__notes__[0]


def test_close_error_after_successful_commit_preserves_outcome(fake, monkeypatch):
    def fail(self):
        raise OSError('close failed')
    db = PostgresDatabase()
    db.execute(CompiledQuery('select'))
    db.commit()
    monkeypatch.setattr(FakeConnection, 'close', fail)
    with pytest.raises(OSError, match='close failed'):
        db.close()
    assert db.outcome == 'committed'


@pytest.mark.parametrize('columns', [(ResultColumn('wrong'),), (ResultColumn('value'), ResultColumn('extra'))])
def test_mismatched_metadata_rolls_back_before_fetch(fake, columns):
    with PostgresDatabase() as db:
        with pytest.raises(ValueError, match='Compiled result columns'):
            db.execute(CompiledQuery('select', columns=columns))
        assert db.outcome == 'rolled_back'
    assert 'fetch' not in [name for name, _ in fake]


def test_supplied_metadata_is_preserved(fake):
    column = ResultColumn('value', 'I', 'sample.value', {'label': 'The value'})
    with PostgresDatabase() as db:
        result = db.execute(CompiledQuery('select', columns=(column,)))
    assert result.columns[0] is column
    assert result.rows == [{'value': 42}]


def test_metadata_without_result_set_fails(fake, monkeypatch):
    original = FakeConnection.execute
    def no_result(self, sql, params):
        original(self, sql, params)
        self.description = None
    monkeypatch.setattr(FakeConnection, 'execute', no_result)
    with PostgresDatabase() as db:
        with pytest.raises(ValueError, match='without a result set'):
            db.execute(CompiledQuery('update', columns=(ResultColumn('value'),)))
    assert [name for name, _ in fake][-2:] == ['rollback', 'close']


def test_autocommit_rejected():
    with pytest.raises(ValueError):
        PostgresDatabase(connect_kwargs={'autocommit': True})


def test_driver_cannot_reenter_execute_or_finish_active_statement(fake, monkeypatch):
    original = FakeConnection.execute
    with PostgresDatabase() as db:
        def callback(self, sql, params):
            original(self, sql, params)
            for operation in (lambda: db.execute(CompiledQuery('recursive')), db.commit, db.rollback, db.close):
                with pytest.raises(TransactionStateError, match='executing'):
                    operation()
        monkeypatch.setattr(FakeConnection, 'execute', callback)
        assert db.execute(CompiledQuery('select')).rowcount == 1
        db.commit()
    assert 'recursive' not in [name for name, _ in fake]
