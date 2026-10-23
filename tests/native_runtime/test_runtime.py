import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel.contracts import CompiledQuery, ResultColumn
from asqueel.runtime import TransactionStateError
from tests.unit_of_work import empty_database


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls
        self.description = [('value',)]
        self.rowcount = 1

    def record(self, name):
        self.calls.append((name, threading.get_ident()))

    def cursor(self, *args, **kwargs):
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
    db = empty_database(implementation='postgres')
    assert not hasattr(db, 'transaction')
    assert not hasattr(db, 'connection')
    result = db.execute(CompiledQuery('select'))
    assert [dict(row) for row in result.fetchall()] == [{'value': 42}]
    assert not any(name == 'commit' for name, _ in fake)
    db.commit()
    db.execute(CompiledQuery('second'))
    db.rollback()
    # The fake connection is also its cursor: closeConnection would close an open cursor too.
    del result
    db.closeConnection()
    names = [name for name, _ in fake]
    assert names.count('connect') == names.count('commit') == names.count('rollback') == names.count('close') == 1
    assert {thread for _, thread in fake} == {threading.get_ident()}


def test_sql_error_rolls_back_and_explicit_retry_reuses_connection(fake):
    db = empty_database(implementation='postgres')
    try:
        db.execute(CompiledQuery('first'))
        with pytest.raises(ValueError, match='statement failed'):
            db.execute(CompiledQuery('error'))
        assert [name for name, _ in fake][-1] == 'rollback'
        db.execute(CompiledQuery('recovered'))
        db.commit()
    finally:
        db.closeConnection()
    assert [name for name, _ in fake].count('connect') == 1


def test_close_connection_discards_pending_work_and_closes_only_current_thread(fake):
    db = empty_database(implementation='postgres')
    db.execute(CompiledQuery('select'))
    def worker():
        try:
            db.execute(CompiledQuery('worker'))
            db.commit()
        finally:
            db.closeConnection()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()
    db.execute(CompiledQuery('still open'))
    db.closeConnection()
    assert [name for name, _ in fake][-2:] == ['rollback', 'close']
    count = len(fake)
    assert db.execute(CompiledQuery('reopened')).rowcount == 1
    db.closeConnection()
    assert [name for name, _ in fake][count] == 'connect'


def test_failed_open_allows_another_attempt(fake, monkeypatch):
    import psycopg
    original = psycopg.connect
    db = empty_database(implementation='postgres')
    try:
        monkeypatch.setattr(psycopg, 'connect', lambda *a, **kw: (_ for _ in ()).throw(OSError('open failed')))
        with pytest.raises(OSError, match='open failed'):
            db.execute(CompiledQuery('select'))
        monkeypatch.setattr(psycopg, 'connect', original)
        assert db.execute(CompiledQuery('select')).rowcount == 1
        db.commit()
    finally:
        db.closeConnection()


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_completion_failure_discards_connection(fake, monkeypatch, operation):
    failure = OSError(f'{operation} failed')
    def fail(self):
        raise failure
    monkeypatch.setattr(FakeConnection, operation, fail)
    db = empty_database(implementation='postgres')
    try:
        db.execute(CompiledQuery('select'))
        with pytest.raises(OSError) as caught:
            getattr(db, operation)()
        assert caught.value is failure
        assert fake[-1][0] == 'close'
    finally:
        db.closeConnection()


def test_commit_error_is_not_masked_by_cleanup_failure(fake, monkeypatch):
    failure = OSError('commit failed')
    def fail_commit(self):
        raise failure
    def fail_close(self):
        raise RuntimeError('close failed')
    monkeypatch.setattr(FakeConnection, 'commit', fail_commit)
    monkeypatch.setattr(FakeConnection, 'close', fail_close)
    db = empty_database(implementation='postgres')
    try:
        db.execute(CompiledQuery('select'))
        with pytest.raises(OSError) as caught:
            db.commit()
        assert caught.value is failure
        assert 'cleanup' in failure.__notes__[0]
    finally:
        db.closeConnection()


def test_close_error_after_successful_commit_keeps_the_commit(fake, monkeypatch):
    def fail(self):
        raise OSError('close failed')
    db = empty_database(implementation='postgres')
    db.execute(CompiledQuery('select'))
    db.commit()
    monkeypatch.setattr(FakeConnection, 'close', fail)
    with pytest.raises(OSError, match='close failed'):
        db.closeConnection()
    names = [name for name, _ in fake]
    assert 'commit' in names
    assert 'rollback' not in names


@pytest.mark.parametrize('columns', [(ResultColumn('wrong'),), (ResultColumn('value'), ResultColumn('extra'))])
def test_mismatched_metadata_rolls_back_before_fetch(fake, columns):
    db = empty_database(implementation='postgres')
    try:
        with pytest.raises(ValueError, match='Compiled result columns'):
            db.execute(CompiledQuery('select', columns=columns))
        assert [name for name, _ in fake][-1] == 'rollback'
    finally:
        db.closeConnection()
    assert 'fetch' not in [name for name, _ in fake]


def test_matching_metadata_reads_the_rows_by_name(fake):
    column = ResultColumn('value', 'I', 'sample.value', {'label': 'The value'})
    db = empty_database(implementation='postgres')
    try:
        rows = db.execute(CompiledQuery('select', columns=(column,))).fetchall()
    finally:
        db.closeConnection()
    assert [dict(row) for row in rows] == [{'value': 42}]


def test_metadata_without_result_set_fails(fake, monkeypatch):
    original = FakeConnection.execute
    def no_result(self, sql, params):
        original(self, sql, params)
        self.description = None
    monkeypatch.setattr(FakeConnection, 'execute', no_result)
    db = empty_database(implementation='postgres')
    try:
        with pytest.raises(ValueError, match='without a result set'):
            db.execute(CompiledQuery('update', columns=(ResultColumn('value'),)))
    finally:
        db.closeConnection()
    assert [name for name, _ in fake][-2:] == ['rollback', 'close']


def test_autocommit_rejected():
    with pytest.raises(ValueError):
        empty_database(implementation='postgres', connect_kwargs={'autocommit': True})


def test_driver_cannot_reenter_execute_or_finish_active_statement(fake, monkeypatch):
    original = FakeConnection.execute
    db = empty_database(implementation='postgres')
    try:
        def callback(self, sql, params):
            original(self, sql, params)
            for operation in (lambda: db.execute(CompiledQuery('recursive')), db.commit, db.rollback,
                              db.closeConnection):
                with pytest.raises(TransactionStateError, match='executing'):
                    operation()
        monkeypatch.setattr(FakeConnection, 'execute', callback)
        assert db.execute(CompiledQuery('select')).rowcount == 1
        db.commit()
    finally:
        db.closeConnection()
    assert 'recursive' not in [name for name, _ in fake]
