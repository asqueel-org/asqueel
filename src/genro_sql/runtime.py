"""Driver-independent async runtime with bounded, transaction-pinned threads."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, cast

from .contracts import CompiledQuery, QueryResult
from .drivers.base import SyncDriver


class DatabaseClosedError(RuntimeError):
    """The database is closing or closed."""


class DatabaseSaturatedError(RuntimeError):
    """All workers and the bounded admission queue are occupied."""


class TransactionStateError(RuntimeError):
    """The transaction cannot accept another operation."""


async def _drain(future: asyncio.Future[Any]) -> Any:
    """Cancellation never abandons synchronous work still owning resources."""
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(future)
            break
        except asyncio.CancelledError:
            cancelled = True
            if future.done():
                # Consume a possible worker exception even when cancellation won.
                try:
                    future.result()
                except BaseException:
                    pass
                raise
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError() from None
            raise
    if cancelled:
        raise asyncio.CancelledError()
    return result


class ThreadedDatabase:
    """A bounded async facade over a synchronous driver.

    Each transaction owns one worker and one fresh connection until cleanup.
    Instances belong to one event loop. Results are eagerly materialized.
    """

    def __init__(self, conninfo: str = '', *, driver: SyncDriver, max_workers: int = 4,
                 max_pending: int = 16, connect_kwargs: dict[str, Any] | None = None):
        if max_workers < 1 or max_pending < 0:
            raise ValueError('max_workers must be positive and max_pending nonnegative')
        self.conninfo = conninfo
        self.driver = driver
        self.connect_kwargs = dict(connect_kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self._executors = [ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'genro-sql-{i}')
                           for i in range(max_workers)]
        self._slots: asyncio.Queue[int] = asyncio.Queue()
        for index in range(max_workers):
            self._slots.put_nowait(index)
        self._max_pending = max_pending
        self._pending = 0
        self._active = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self._closing = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._owners: dict[asyncio.Task[Any], int] = {}

    def _check_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError('ThreadedDatabase belongs to a different event loop')

    async def _acquire(self) -> int:
        self._check_loop()
        if self._closing:
            raise DatabaseClosedError('Database is closing or closed')
        task = asyncio.current_task()
        if task is not None and self._owners.get(task, 0):
            raise TransactionStateError('Nested database transactions are unsupported; use tx.execute')
        try:
            slot = self._slots.get_nowait()
        except asyncio.QueueEmpty:
            if self._pending >= self._max_pending:
                raise DatabaseSaturatedError('Database worker admission queue is full') from None
            self._pending += 1
            try:
                slot = await self._slots.get()
            finally:
                self._pending -= 1
        if self._closing:
            self._slots.put_nowait(slot)
            raise DatabaseClosedError('Database is closing or closed')
        self._active += 1
        self._idle.clear()
        return slot

    def _release(self, slot: int) -> None:
        self._slots.put_nowait(slot)
        self._active -= 1
        if self._active == 0:
            self._idle.set()

    async def _run(self, slot: int, function: Callable[..., Any], *args: Any) -> Any:
        future = asyncio.get_running_loop().run_in_executor(
            self._executors[slot], partial(function, *args))
        return await _drain(future)

    def transaction(self) -> Transaction:
        return Transaction(self)

    async def execute(self, query: CompiledQuery) -> QueryResult:
        self.driver.validate(query)
        async with self.transaction() as transaction:
            return await transaction.execute(query)

    async def __aenter__(self) -> ThreadedDatabase:
        self._check_loop()
        if self._closing:
            raise DatabaseClosedError('Database is closing or closed')
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._check_loop()
        task = asyncio.current_task()
        if task is not None and self._owners.get(task, 0):
            raise TransactionStateError('Exit your transaction before closing its database')
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown())
        await _drain(self._close_task)

    async def _shutdown(self) -> None:
        await self._idle.wait()
        for executor in self._executors:
            await asyncio.to_thread(executor.shutdown, wait=True)


class PostgresDatabase(ThreadedDatabase):
    """Compatibility facade selecting the PostgreSQL psycopg driver profile."""

    def __init__(self, conninfo: str = '', *, max_workers: int = 4,
                 max_pending: int = 16, connect_kwargs: dict[str, Any] | None = None,
                 driver: SyncDriver | None = None):
        if driver is None:
            from .drivers.psycopg import PsycopgDriver
            driver = PsycopgDriver()
        if (driver.dialect, driver.binding) != ('postgresql', 'psycopg_named'):
            raise ValueError('PostgresDatabase requires the postgresql/psycopg_named driver profile')
        super().__init__(conninfo, driver=driver, max_workers=max_workers,
                         max_pending=max_pending, connect_kwargs=connect_kwargs)


class Transaction:
    """Single-use transaction; a failed or cancelled statement makes it rollback-only."""

    def __init__(self, database: ThreadedDatabase):
        self.database = database
        self.outcome = 'not_started'
        self._slot: int | None = None
        self._connection: Any = None
        self._used = False
        self._failed = False
        self._finished = False
        self._accepting = False
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task[Any] | None = None

    def _open(self) -> None:
        self._connection = self.database.driver.connect(
            self.database.conninfo, **self.database.connect_kwargs)
        self.outcome = 'active'

    async def __aenter__(self) -> Transaction:
        if self._used:
            raise TransactionStateError('Transaction contexts are single-use')
        self._used = True
        self._slot = await self.database._acquire()
        self._owner = asyncio.current_task()
        if self._owner is not None:
            self.database._owners[self._owner] = self.database._owners.get(self._owner, 0) + 1
        try:
            await self.database._run(self._slot, self._open)
        except BaseException:
            try:
                await self.database._run(self._slot, self._finish, False)
            finally:
                self._release()
            raise
        self._accepting = True
        return self

    async def execute(self, query: CompiledQuery) -> QueryResult:
        self.database.driver.validate(query)
        async with self._lock:
            if self._slot is None or not self._accepting or self._finished or self._failed:
                raise TransactionStateError('Transaction is not active or is rollback-only')
            try:
                return cast(QueryResult, await self.database._run(
                    self._slot, self.database.driver.execute, self._connection, query))
            except BaseException:
                self._failed = True
                raise

    def _finish(self, commit: bool) -> None:
        if self._connection is None:
            return
        try:
            if commit:
                try:
                    self.database.driver.commit(self._connection)
                    self.outcome = 'committed'
                except BaseException:
                    self.outcome = 'unknown'
                    raise
            else:
                try:
                    self.database.driver.rollback(self._connection)
                    self.outcome = 'rolled_back'
                except BaseException:
                    self.outcome = 'unknown'
                    raise
        finally:
            self.database.driver.close(self._connection)
            self._connection = None

    def _release(self) -> None:
        self._finished = True
        if self._slot is not None:
            self.database._release(self._slot)
            self._slot = None
        if self._owner is not None:
            count = self.database._owners[self._owner] - 1
            if count:
                self.database._owners[self._owner] = count
            else:
                del self.database._owners[self._owner]

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self._accepting:
            raise TransactionStateError('Transaction is not active or is already exiting')
        self._accepting = False
        # A dedicated task makes cleanup survive repeated cancellation of the caller.
        cleanup = asyncio.create_task(self._exit(exc_type is None))
        await _drain(cleanup)

    async def _exit(self, success: bool) -> None:
        async with self._lock:
            if self._slot is None or self._finished:
                raise TransactionStateError('Transaction is not active')
            try:
                await self.database._run(self._slot, self._finish, success and not self._failed)
                if success and self._failed:
                    raise TransactionStateError('Transaction rolled back after a failed statement')
            finally:
                self._release()
