"""Lazy synchronous unit of work for cooperating application table operations."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

from .contracts import CompiledQuery, QueryResult
from .drivers.base import SyncDriver
from .environment import SqlEnvironment
from .runtime import Database, Transaction, TransactionStateError


class Session:
    """Retain one transaction until explicit completion or scope exit.

    Construction and an empty transaction scope perform no database I/O.
    Unlike the low-level Database.execute convenience, execute never commits.
    """

    def __init__(self, driver: SyncDriver, conninfo: str = '', *,
                 connect_kwargs: dict[str, Any] | None = None,
                 environment: SqlEnvironment | None = None):
        self.environment = environment if environment is not None else SqlEnvironment()
        self._runtime = Database(conninfo, driver=driver, connect_kwargs=connect_kwargs,
                                 environment=self.environment)
        self._transaction: Transaction | None = None
        self._scope_active = False
        self._failed = False
        self._executing = False
        self._closed = False
        self.outcome = 'not_started'

    def _check_open(self) -> None:
        self._runtime._check_open()

    def _check_available(self) -> None:
        self._check_open()
        if self._executing:
            raise TransactionStateError('Session is already executing an operation')

    def _check_manual_completion(self) -> None:
        self._check_available()
        if self._scope_active:
            raise TransactionStateError('The transaction context owns session completion')

    def _check_usable(self) -> None:
        self._check_available()
        if self._failed:
            raise TransactionStateError('Session is rollback-only; call rollback before reuse')

    def execute(self, query: CompiledQuery) -> QueryResult:
        self._check_usable()
        # Query validation must not acquire a connection or start a transaction.
        self._runtime._validate_query(query)
        self._executing = True
        try:
            if self._transaction is None:
                self._transaction = self._runtime.transaction().__enter__()
                self.outcome = 'active'
            return self._transaction.execute(query)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._executing = False

    def mark_failed(self) -> None:
        """Mark a failed domain operation even when no SQL has run yet."""
        self._check_open()
        self._failed = True

    def _finish(self, commit: bool) -> None:
        transaction = self._transaction
        if transaction is None:
            self._failed = False
            return
        self._executing = True
        try:
            transaction.__exit__(None if commit else Exception, None, None)
        except BaseException:
            self._failed = True
            raise
        else:
            self._failed = False
        finally:
            self.outcome = transaction.outcome
            self._transaction = None
            self._executing = False

    def commit(self) -> None:
        self._check_manual_completion()
        if self._failed:
            raise TransactionStateError('Session is rollback-only; call rollback before reuse')
        self._finish(True)

    def rollback(self) -> None:
        self._check_manual_completion()
        self._finish(False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        self._check_available()
        if self._scope_active:
            raise TransactionStateError('Nested session transaction contexts are unsupported')
        if self._transaction is not None or self._failed:
            raise TransactionStateError('Complete the pending session before entering a transaction context')
        self._scope_active = True
        try:
            try:
                yield self
            except BaseException:
                self._finish(False)
                raise
            else:
                failed = self._failed
                self._finish(not failed)
                if failed:
                    raise TransactionStateError('Session transaction rolled back after a failed operation')
        finally:
            self._scope_active = False

    def close(self) -> None:
        self._runtime._check_owner()
        if self._closed:
            return
        self._check_manual_completion()
        try:
            self._finish(False)
        finally:
            self._runtime.close()
            self._closed = True
