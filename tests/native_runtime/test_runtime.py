import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from genro_sql.contracts import CompiledQuery, ResultColumn
from genro_sql.runtime import DatabaseClosedError, PostgresDatabase, TransactionStateError


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


def test_sync_transaction_runs_entirely_on_calling_thread(fake):
    with PostgresDatabase() as db:
        with db.transaction() as tx:
            result = tx.execute(CompiledQuery('select'))
            assert result.rows == [{'value': 42}]
            assert result.columns[0].name == 'value'
        assert tx.outcome == 'committed'
    assert {thread for _, thread in fake} == {threading.get_ident()}
    assert [name for name, _ in fake][-2:] == ['commit', 'close']


def test_caught_error_is_rollback_only_and_exit_is_not_silent(fake):
    with PostgresDatabase() as db:
        with pytest.raises(TransactionStateError, match='rolled back'):
            with db.transaction() as tx:
                with pytest.raises(ValueError):
                    tx.execute(CompiledQuery('error'))
                with pytest.raises(TransactionStateError):
                    tx.execute(CompiledQuery('select'))
        assert tx.outcome == 'rolled_back'
        assert db.execute(CompiledQuery('select')).rowcount == 1


def test_body_exception_rolls_back_and_closes(fake):
    with PostgresDatabase() as db:
        with pytest.raises(RuntimeError, match='application failed'):
            with db.transaction() as tx:
                tx.execute(CompiledQuery('select'))
                raise RuntimeError('application failed')
        assert tx.outcome == 'rolled_back'
    assert [name for name, _ in fake][-2:] == ['rollback', 'close']


def test_close_and_nested_transactions_fail_closed(fake):
    with PostgresDatabase() as db:
        with db.transaction() as tx:
            with pytest.raises(TransactionStateError, match='active transaction'):
                db.close()
            with pytest.raises(TransactionStateError, match='Nested'):
                db.execute(CompiledQuery('select'))
            with pytest.raises(TransactionStateError, match='Nested'):
                with db.transaction():
                    pass
            assert tx.execute(CompiledQuery('select')).rowcount == 1
    db.close()
    with pytest.raises(DatabaseClosedError):
        db.execute(CompiledQuery('select'))


def test_transaction_is_single_use_and_cannot_execute_after_exit(fake):
    with PostgresDatabase() as db:
        tx = db.transaction()
        with pytest.raises(TransactionStateError):
            tx.execute(CompiledQuery('select'))
        with tx:
            pass
        with pytest.raises(TransactionStateError):
            tx.execute(CompiledQuery('select'))
        with pytest.raises(TransactionStateError):
            tx.__exit__(None, None, None)
        with pytest.raises(TransactionStateError, match='single-use'):
            with tx:
                pass


def test_cross_thread_database_and_transaction_use_is_rejected(fake):
    with PostgresDatabase() as db, ThreadPoolExecutor(max_workers=1) as executor:
        with db.transaction() as tx:
            for operation in (lambda: tx.execute(CompiledQuery('select')),
                              lambda: db.execute(CompiledQuery('select')),
                              db.close, lambda: tx.__exit__(None, None, None)):
                with pytest.raises(TransactionStateError, match='constructing thread'):
                    executor.submit(operation).result()
            assert tx.execute(CompiledQuery('select')).rowcount == 1
    assert {thread for _, thread in fake} == {threading.get_ident()}


def test_failed_open_releases_database_for_another_attempt(fake, monkeypatch):
    import psycopg
    original = psycopg.connect
    with PostgresDatabase() as db:
        monkeypatch.setattr(psycopg, 'connect', lambda *a, **kw: (_ for _ in ()).throw(OSError('open failed')))
        with pytest.raises(OSError, match='open failed'):
            db.execute(CompiledQuery('select'))
        monkeypatch.setattr(psycopg, 'connect', original)
        assert db.execute(CompiledQuery('select')).rowcount == 1


@pytest.mark.parametrize('operation', ['commit', 'rollback'])
def test_cleanup_after_transaction_control_failure(fake, monkeypatch, operation):
    failure = OSError(f'{operation} failed')

    def fail(self):
        raise failure

    monkeypatch.setattr(FakeConnection, operation, fail)
    with PostgresDatabase() as db:
        tx = db.transaction()
        with pytest.raises(OSError) as caught:
            with tx:
                if operation == 'rollback':
                    raise RuntimeError('body error')
        assert caught.value is failure
        assert tx.outcome == 'unknown'
        assert fake[-1][0] == 'close'


def test_commit_error_is_not_masked_by_cleanup_error(fake, monkeypatch):
    failure = OSError('commit failed')

    def fail_commit(self):
        raise failure

    def fail_close(self):
        raise RuntimeError('close failed')

    monkeypatch.setattr(FakeConnection, 'commit', fail_commit)
    monkeypatch.setattr(FakeConnection, 'close', fail_close)
    with PostgresDatabase() as db:
        with pytest.raises(OSError) as caught:
            with db.transaction() as tx:
                pass
        assert caught.value is failure
        assert tx.outcome == 'unknown'
        assert 'cleanup' in failure.__notes__[0]


def test_close_error_after_successful_commit_preserves_outcome(fake, monkeypatch):
    def fail(self):
        raise OSError('close failed')
    monkeypatch.setattr(FakeConnection, 'close', fail)
    with PostgresDatabase() as db:
        with pytest.raises(OSError, match='close failed'):
            with db.transaction() as tx:
                pass
        assert tx.outcome == 'committed'


@pytest.mark.parametrize('columns', [(ResultColumn('wrong'),), (ResultColumn('value'), ResultColumn('extra'))])
def test_mismatched_result_metadata_rolls_back_before_fetch(fake, columns):
    with PostgresDatabase() as db:
        with pytest.raises(ValueError, match='Compiled result columns'):
            with db.transaction() as tx:
                tx.execute(CompiledQuery('select', columns=columns))
        assert tx.outcome == 'rolled_back'
    assert 'fetch' not in [name for name, _ in fake]


def test_supplied_result_metadata_is_preserved_when_names_match(fake):
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


def test_driver_callback_cannot_reenter_execute_or_finish_active_statement(fake, monkeypatch):
    original = FakeConnection.execute
    with PostgresDatabase() as db:
        with db.transaction() as tx:
            def callback(self, sql, params):
                original(self, sql, params)
                with pytest.raises(TransactionStateError, match='executing'):
                    tx.execute(CompiledQuery('recursive'))
                with pytest.raises(TransactionStateError, match='executing'):
                    tx.__exit__(None, None, None)
            monkeypatch.setattr(FakeConnection, 'execute', callback)
            assert tx.execute(CompiledQuery('select')).rowcount == 1
        assert tx.outcome == 'committed'
    names = [name for name, _ in fake]
    assert 'recursive' not in names
    assert names.count('commit') == names.count('close') == 1
