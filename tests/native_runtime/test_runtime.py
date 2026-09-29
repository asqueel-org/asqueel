import asyncio
import threading
from types import SimpleNamespace

import pytest

from genro_sql.contracts import CompiledQuery, ResultColumn
from genro_sql.runtime import (
    DatabaseClosedError, DatabaseSaturatedError, PostgresDatabase, TransactionStateError,
)


class FakeConnection:
    def __init__(self, calls, started, proceed):
        self.calls = calls
        self.started = started
        self.proceed = proceed
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
        if sql == 'slow':
            self.started.set()
            assert self.proceed.wait(5)
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
    started = threading.Event()
    proceed = threading.Event()

    def connect(*args, **kwargs):
        connection = FakeConnection(calls, started, proceed)
        connection.record('connect')
        return connection

    monkeypatch.setattr(psycopg, 'connect', connect)
    return calls, started, proceed


async def wait_started(event):
    for _ in range(500):
        if event.is_set():
            return
        await asyncio.sleep(.001)
    raise AssertionError('worker did not start')


def test_transaction_pins_every_operation_to_worker(fake):
    async def scenario():
        async with PostgresDatabase(max_workers=1) as db:
            async with db.transaction() as tx:
                result = await tx.execute(CompiledQuery('select'))
                assert result.rows == [{'value': 42}]
                assert result.columns[0].name == 'value'
            assert tx.outcome == 'committed'
        calls = fake[0]
        assert len({thread for _, thread in calls}) == 1
        assert calls[0][1] != threading.get_ident()
        assert [name for name, _ in calls][-2:] == ['commit', 'close']
    asyncio.run(scenario())


def test_error_is_rollback_only_even_when_caught(fake):
    async def scenario():
        async with PostgresDatabase() as db:
            with pytest.raises(TransactionStateError, match='rolled back'):
                async with db.transaction() as tx:
                    with pytest.raises(ValueError):
                        await tx.execute(CompiledQuery('error'))
                    with pytest.raises(TransactionStateError):
                        await tx.execute(CompiledQuery('select'))
            assert tx.outcome == 'rolled_back'
        assert 'commit' not in [name for name, _ in fake[0]]
    asyncio.run(scenario())


def test_cancelled_query_drains_before_slot_release(fake):
    async def scenario():
        calls, started, proceed = fake
        async with PostgresDatabase(max_workers=1, max_pending=0) as db:
            task = asyncio.create_task(db.execute(CompiledQuery('slow')))
            await wait_started(started)
            task.cancel()
            await asyncio.sleep(.01)
            task.cancel()
            with pytest.raises(DatabaseSaturatedError):
                await db.execute(CompiledQuery('select'))
            assert not task.done()
            proceed.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert [name for name, _ in calls][-2:] == ['rollback', 'close']
            assert (await db.execute(CompiledQuery('select'))).rowcount == 1
    asyncio.run(scenario())


def test_bounded_admission_and_cancelled_waiter(fake):
    async def scenario():
        async with PostgresDatabase(max_workers=1, max_pending=1) as db:
            async with db.transaction():
                waiting = asyncio.create_task(db.execute(CompiledQuery('select')))
                await asyncio.sleep(0)
                with pytest.raises(DatabaseSaturatedError):
                    await asyncio.create_task(db.execute(CompiledQuery('select')))
                waiting.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiting
            assert (await db.execute(CompiledQuery('select'))).rowcount == 1
    asyncio.run(scenario())


def test_close_waits_for_active_work_and_rejects_admission(fake):
    async def scenario():
        db = PostgresDatabase(max_workers=1)
        task = asyncio.create_task(db.execute(CompiledQuery('slow')))
        await wait_started(fake[1])
        closing = asyncio.create_task(db.aclose())
        await asyncio.sleep(0)
        assert not closing.done()
        with pytest.raises(DatabaseClosedError):
            await db.execute(CompiledQuery('select'))
        fake[2].set()
        await task
        await closing
        await db.aclose()
    asyncio.run(scenario())


def test_close_inside_owned_transaction_fails_instead_of_deadlocking(fake):
    async def scenario():
        async with PostgresDatabase() as db:
            async with db.transaction():
                with pytest.raises(TransactionStateError):
                    await db.aclose()
    asyncio.run(scenario())


def test_cancelled_exit_waits_for_commit_and_reports_actual_outcome(fake, monkeypatch):
    started, proceed = threading.Event(), threading.Event()
    original = FakeConnection.commit

    def slow_commit(self):
        started.set()
        assert proceed.wait(5)
        original(self)

    monkeypatch.setattr(FakeConnection, 'commit', slow_commit)

    async def scenario():
        db = PostgresDatabase(max_workers=1, max_pending=0)
        tx = db.transaction()

        async def transaction():
            async with tx:
                await tx.execute(CompiledQuery('select'))

        task = asyncio.create_task(transaction())
        await wait_started(started)
        task.cancel()
        await asyncio.sleep(.01)
        task.cancel()
        assert not task.done()
        with pytest.raises(DatabaseSaturatedError):
            await db.execute(CompiledQuery('select'))
        proceed.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert tx.outcome == 'committed'
        assert fake[0][-1][0] == 'close'
        await db.aclose()
    asyncio.run(scenario())


def test_commit_failure_has_unknown_outcome(fake, monkeypatch):
    def broken_commit(self):
        raise OSError('connection lost while committing')
    monkeypatch.setattr(FakeConnection, 'commit', broken_commit)

    async def scenario():
        async with PostgresDatabase() as db:
            tx = db.transaction()
            with pytest.raises(OSError):
                async with tx:
                    await tx.execute(CompiledQuery('select'))
            assert tx.outcome == 'unknown'
            assert fake[0][-1][0] == 'close'
    asyncio.run(scenario())


def test_constructor_limits():
    for kwargs in ({'max_workers': 0}, {'max_pending': -1}, {'connect_kwargs': {'autocommit': True}}):
        with pytest.raises(ValueError):
            PostgresDatabase(**kwargs)


def test_cancelled_open_closes_connection_before_reusing_worker(fake, monkeypatch):
    import psycopg
    original = psycopg.connect
    started, proceed = threading.Event(), threading.Event()

    def slow_open(*args, **kwargs):
        started.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(psycopg, 'connect', slow_open)

    async def scenario():
        async with PostgresDatabase(max_workers=1, max_pending=0) as db:
            task = asyncio.create_task(db.execute(CompiledQuery('select')))
            await wait_started(started)
            task.cancel()
            await asyncio.sleep(.01)
            assert not task.done()
            proceed.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert [name for name, _ in fake[0]] == ['connect', 'rollback', 'close']
            assert (await db.execute(CompiledQuery('select'))).rows == [{'value': 42}]
    asyncio.run(scenario())


def test_cancelled_exit_drains_rollback(fake, monkeypatch):
    started, proceed = threading.Event(), threading.Event()
    original = FakeConnection.rollback

    def slow_rollback(self):
        started.set()
        assert proceed.wait(5)
        original(self)

    monkeypatch.setattr(FakeConnection, 'rollback', slow_rollback)

    async def scenario():
        async with PostgresDatabase(max_workers=1, max_pending=0) as db:
            tx = db.transaction()

            async def operation():
                async with tx:
                    raise ValueError('rollback required')

            task = asyncio.create_task(operation())
            await wait_started(started)
            task.cancel()
            await asyncio.sleep(.01)
            task.cancel()
            assert not task.done()
            proceed.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert tx.outcome == 'rolled_back'
            assert fake[0][-1][0] == 'close'
    asyncio.run(scenario())


def test_nested_acquisition_is_rejected_without_waiting(fake):
    async def scenario():
        async with PostgresDatabase(max_workers=1) as db:
            async with db.transaction() as tx:
                with pytest.raises(TransactionStateError, match='Nested'):
                    await db.execute(CompiledQuery('select'))
                with pytest.raises(TransactionStateError, match='Nested'):
                    async with db.transaction():
                        pass
                assert (await tx.execute(CompiledQuery('select'))).rows == [{'value': 42}]
    asyncio.run(scenario())


def test_exit_started_rejects_late_statement_before_cleanup_task_runs(fake):
    async def scenario():
        async with PostgresDatabase(max_workers=1) as db:
            tx = await db.transaction().__aenter__()
            exiting = asyncio.create_task(tx.__aexit__(None, None, None))
            # __aexit__ starts and schedules its cancellation-protected cleanup.
            # This task resumes before that cleanup task has acquired the lock.
            await asyncio.sleep(0)
            try:
                with pytest.raises(TransactionStateError):
                    await tx.execute(CompiledQuery('late_statement'))
            finally:
                await exiting
            assert 'late_statement' not in [name for name, _ in fake[0]]
            with pytest.raises(TransactionStateError):
                await tx.__aexit__(None, None, None)
    asyncio.run(scenario())


@pytest.mark.parametrize('columns', [
    (ResultColumn('wrong'),),
    (ResultColumn('value'), ResultColumn('extra')),
])
def test_mismatched_result_metadata_rolls_back_before_fetch(fake, columns):
    async def scenario():
        async with PostgresDatabase() as db:
            tx = db.transaction()
            with pytest.raises(ValueError, match='Compiled result columns'):
                async with tx:
                    await tx.execute(CompiledQuery('select', columns=columns))
            assert tx.outcome == 'rolled_back'
        names = [name for name, _ in fake[0]]
        assert 'fetch' not in names
        assert names[-3:] == ['cursor_close', 'rollback', 'close']
    asyncio.run(scenario())


def test_supplied_result_metadata_is_preserved_when_names_match(fake):
    async def scenario():
        column = ResultColumn('value', 'I', 'sample.value', {'label': 'The value'})
        async with PostgresDatabase() as db:
            result = await db.execute(CompiledQuery('select', columns=(column,)))
        assert result.columns == (column,)
        assert result.columns[0] is column
        assert result.rows == [{'value': 42}]
    asyncio.run(scenario())


def test_metadata_on_nonreturning_statement_fails_and_rolls_back(fake, monkeypatch):
    original = FakeConnection.execute

    def no_result(self, sql, params):
        original(self, sql, params)
        self.description = None

    monkeypatch.setattr(FakeConnection, 'execute', no_result)

    async def scenario():
        async with PostgresDatabase() as db:
            with pytest.raises(ValueError, match='without a result set'):
                await db.execute(CompiledQuery('update', columns=(ResultColumn('value'),)))
        names = [name for name, _ in fake[0]]
        assert 'fetch' not in names
        assert names[-2:] == ['rollback', 'close']
    asyncio.run(scenario())
