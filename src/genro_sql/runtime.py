"""Synchronous, thread-owned database runtime over an injected data driver."""
from __future__ import annotations

from threading import get_ident
from typing import Any

from .contracts import CompiledQuery, QueryResult
from .drivers.base import SyncDriver
from .environment import SqlEnvironment


class DatabaseClosedError(RuntimeError):
    """The database has been closed."""


class TransactionStateError(RuntimeError):
    """The database or transaction cannot accept this operation."""


class Database:
    """Synchronous database facade owned by its constructing thread.

    One transaction may be active at a time. Each transaction opens a fresh
    connection and closes it on exit. Results are eagerly materialized.
    """

    def __init__(self, conninfo: str = '', *, driver: SyncDriver,
                 connect_kwargs: dict[str, Any] | None = None,
                 environment: SqlEnvironment | None = None):
        self.conninfo = conninfo
        self.driver = driver
        self.environment = environment if environment is not None else SqlEnvironment()
        self.connect_kwargs = dict(connect_kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self._owner = get_ident()
        self._active: Transaction | None = None
        self._closed = False

    @property
    def current_env(self):
        return self.environment.current_env

    @property
    def currentEnv(self):
        return self.current_env

    def temp_env(self, **values: Any):
        return self.environment.temp_env(**values)

    def tempEnv(self, **values: Any):
        return self.temp_env(**values)

    def _check_owner(self) -> None:
        if get_ident() != self._owner:
            raise TransactionStateError('Database operations must run on the constructing thread')

    def _check_open(self) -> None:
        self._check_owner()
        if self._closed:
            raise DatabaseClosedError('Database is closed')

    def _validate_query(self, query: CompiledQuery) -> None:
        self.driver.validate(query)
        if query.environment is not None:
            query.environment.validate(self.environment.snapshot())

    def transaction(self) -> Transaction:
        self._check_open()
        return Transaction(self)

    def execute(self, query: CompiledQuery) -> QueryResult:
        self._check_open()
        self._validate_query(query)
        with self.transaction() as transaction:
            return transaction.execute(query)

    def __enter__(self) -> Database:
        self._check_open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._check_owner()
        if self._active is not None:
            raise TransactionStateError('Exit the active transaction before closing its database')
        self._closed = True


class PostgresDatabase(Database):
    """Compatibility facade selecting the PostgreSQL psycopg driver profile."""

    def __init__(self, conninfo: str = '', *, connect_kwargs: dict[str, Any] | None = None,
                 driver: SyncDriver | None = None, environment: SqlEnvironment | None = None):
        if driver is None:
            from .drivers.psycopg import PsycopgDriver
            driver = PsycopgDriver()
        if (driver.dialect, driver.binding) != ('postgresql', 'psycopg_named'):
            raise ValueError('PostgresDatabase requires the postgresql/psycopg_named driver profile')
        super().__init__(conninfo, driver=driver, connect_kwargs=connect_kwargs,
                         environment=environment)


class Transaction:
    """Single-use transaction; a failed statement makes it rollback-only."""

    def __init__(self, database: Database):
        self.database = database
        self.outcome = 'not_started'
        self._connection: Any = None
        self._used = False
        self._failed = False
        self._accepting = False
        self._executing = False

    def __enter__(self) -> Transaction:
        self.database._check_open()
        if self._used:
            raise TransactionStateError('Transaction contexts are single-use')
        if self.database._active is not None:
            raise TransactionStateError('Nested database transactions are unsupported; use tx.execute')
        self._used = True
        self.database._active = self
        try:
            self._connection = self.database.driver.connect(
                self.database.conninfo, **self.database.connect_kwargs)
        except BaseException:
            self.database._active = None
            raise
        self.outcome = 'active'
        self._accepting = True
        return self

    def execute(self, query: CompiledQuery) -> QueryResult:
        self.database._check_open()
        if self._executing:
            raise TransactionStateError('Transaction is already executing a statement')
        if not self._accepting or self._failed or self.database._active is not self:
            raise TransactionStateError('Transaction is not active or is rollback-only')
        self.database._validate_query(query)
        self._executing = True
        try:
            return self.database.driver.execute(self._connection, query)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._executing = False

    def _finish(self, commit: bool) -> None:
        error: BaseException | None = None
        try:
            if commit:
                self.database.driver.commit(self._connection)
                self.outcome = 'committed'
            else:
                self.database.driver.rollback(self._connection)
                self.outcome = 'rolled_back'
        except BaseException as operation_error:
            self.outcome = 'unknown'
            error = operation_error
        try:
            self.database.driver.close(self._connection)
        except BaseException as close_error:
            if error is None:
                error = close_error
            else:
                error.add_note(f'Connection cleanup also failed: {type(close_error).__name__}')
        finally:
            self._connection = None
        if error is not None:
            raise error

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.database._check_owner()
        if self._executing:
            raise TransactionStateError('Cannot exit while the transaction is executing a statement')
        if not self._accepting or self.database._active is not self:
            raise TransactionStateError('Transaction is not active or is already exiting')
        self._accepting = False
        try:
            self._finish(exc_type is None and not self._failed)
            if exc_type is None and self._failed:
                raise TransactionStateError('Transaction rolled back after a failed statement')
        finally:
            self.database._active = None
