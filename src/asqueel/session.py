"""Lazy synchronous application session retaining its physical connection."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from .contracts import CompiledQuery, QueryResult
from .drivers.base import SyncDriver
from .environment import SqlEnvironment
from .runtime import Database, TransactionStateError


class DeferredCommitError(RuntimeError):
    """One or more errors deliberately queued for the commit boundary."""


class Session:
    """One named unit of work; commit/rollback retain the connection for reuse.

    SQL execution errors immediately roll back, as in legacy GnrSqlDb.execute.
    Python domain failures remain rollback-only until explicitly cleared. An
    optional transaction scope cannot silently succeed after a caught SQL error.
    """

    def __init__(self, driver: SyncDriver, conninfo: str = '', *,
                 connect_kwargs: dict[str, Any] | None = None,
                 environment: SqlEnvironment | None = None,
                 connection_name: str | None = None):
        self.environment = environment if environment is not None else SqlEnvironment()
        self._runtime = Database(conninfo, driver=driver, connect_kwargs=connect_kwargs,
                                 environment=self.environment)
        self._connection: Any = None
        self._pending = False
        self._committing = False
        self._completion_failed = False
        self._connection_name = connection_name
        self._scope_active = False
        self._scope_failed = False
        self._failed = False
        self._executing = False
        self._closed = False
        self._execution_error: BaseException | None = None
        self._execution_count = 0
        self._deferred: dict[str, dict[str, dict[tuple[int, str], tuple[Any, tuple, dict]]]] = {
            'before': {}, 'after': {},
        }
        self._pending_exceptions: list[BaseException] = []
        self.outcome = 'not_started'

    def _defer(self, queue: str, callback, *args, **kwargs):
        self._check_usable()
        block = kwargs.pop('_deferredBlock', None) or '_base_'
        deferred_id = kwargs.pop('_deferredId', None)
        if not deferred_id:
            deferred_id = uuid4().hex
        entries = self._deferred[queue].setdefault(block, {})
        key = (id(callback), str(deferred_id))
        if key not in entries:
            entries[key] = (callback, args, kwargs)
            return kwargs
        return entries[key][2]

    def defer_to_commit(self, callback, *args, **kwargs):
        return self._defer('before', callback, *args, **kwargs)

    def defer_after_commit(self, callback, *args, **kwargs):
        return self._defer('after', callback, *args, **kwargs)

    def deferred_raise(self, exception: BaseException) -> None:
        self._check_usable()
        if not isinstance(exception, BaseException):
            raise TypeError('deferred_raise requires an exception instance')
        self._pending_exceptions.append(exception)

    def _invoke_deferred(self, queue: str) -> None:
        context: dict[str, Any] = {'onCommittingStep': True}
        if self._connection_name is not None:
            context['connectionName'] = self._connection_name
        with self.environment.temp_env(**context):
            self._drain_deferred(queue)

    def _drain_deferred(self, queue: str) -> None:
        blocks = self._deferred[queue]
        while blocks:
            block_name = sorted(blocks)[0]
            entries = blocks[block_name]
            while entries:
                key = next(iter(entries))
                callback, args, kwargs = entries.pop(key)
                callback(*args, **kwargs)
                self._check_usable()
                if not getattr(callback, 'deferredCommitRecursion', False):
                    entries.pop(key, None)
            blocks.pop(block_name, None)

    def _clear_deferred(self) -> None:
        self._deferred['before'].clear()
        self._deferred['after'].clear()
        self._pending_exceptions.clear()

    def _check_open(self) -> None:
        self._runtime._check_open()

    def _check_available(self) -> None:
        self._check_open()
        if self._executing:
            raise TransactionStateError('Session is already executing an operation')

    def _check_manual_completion(self) -> None:
        self._check_available()
        if self._committing:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')
        if self._scope_active:
            raise TransactionStateError('The transaction context owns session completion')

    def _check_usable(self) -> None:
        self._check_available()
        if self._failed or self._completion_failed or (self._scope_active and self._scope_failed):
            raise TransactionStateError('Session is rollback-only; call rollback before reuse')

    def execute(self, query: CompiledQuery) -> QueryResult:
        self._check_usable()
        self._runtime._validate_query(query)
        self._execution_count += 1
        self._executing = True
        self._execution_error = None
        try:
            if self._connection is None:
                self._connection = self._runtime.driver.connect(
                    self._runtime.conninfo, **self._runtime.connect_kwargs)
            self._pending = True
            self.outcome = 'active'
            return self._runtime.driver.execute(self._connection, query)
        except BaseException as error:
            self._execution_error = error
            self._completion_failed = self._committing
            self._scope_failed = self._scope_active
            try:
                self._finish(False)
            except BaseException as cleanup_error:
                # The original execution error must remain catchable by callers.
                error.add_note(f'Automatic rollback failed: {type(cleanup_error).__name__}')
                raise error from cleanup_error
            raise
        finally:
            self._executing = False

    def mark_failed(self) -> None:
        """Mark a failed domain operation even when no SQL has run yet."""
        self._check_open()
        self._failed = True

    def _discard_connection(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            self._runtime.driver.close(connection)

    def _finish(self, commit: bool) -> None:
        if not self._pending:
            if self.outcome != 'unknown':
                self._failed = False
            if not commit:
                self._clear_deferred()
            return
        self._executing = True
        try:
            operation = self._runtime.driver.commit if commit else self._runtime.driver.rollback
            operation(self._connection)
            self.outcome = 'committed' if commit else 'rolled_back'
            self._failed = False
        except BaseException as error:
            self.outcome = 'unknown'
            self._failed = True
            try:
                self._discard_connection()
            except BaseException as close_error:
                error.add_note(f'Connection cleanup also failed: {type(close_error).__name__}')
            raise
        finally:
            self._pending = False
            self._executing = False
            if not commit or self.outcome == 'unknown':
                self._clear_deferred()

    def _commit_pending(self) -> None:
        if self._committing:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')
        self._committing = True
        self._completion_failed = False
        try:
            while self._pending:
                try:
                    self._invoke_deferred('before')
                    self._check_usable()
                    if self._pending_exceptions:
                        messages = '\n'.join(str(error) for error in self._pending_exceptions)
                        raise DeferredCommitError(messages)
                except BaseException:
                    self._failed = True
                    raise
                self._pending_exceptions.clear()
                self._finish(True)
                try:
                    self._invoke_deferred('after')
                except BaseException:
                    # The preceding transaction is committed and cannot be undone.
                    # A callback may have opened a new transaction: retain its
                    # failure until the caller rolls it back.
                    if self._pending:
                        self._failed = True
                    self._clear_deferred()
                    raise
        finally:
            self._committing = False
            self._completion_failed = False

    def commit(self) -> None:
        self._check_manual_completion()
        if self._failed:
            raise TransactionStateError('Session is rollback-only; call rollback before reuse')
        self._commit_pending()

    def rollback(self) -> None:
        self._check_manual_completion()
        self._finish(False)
        self._failed = False

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        self._check_available()
        if self._scope_active:
            raise TransactionStateError('Nested session transaction contexts are unsupported')
        if self._pending or self._failed:
            raise TransactionStateError('Complete the pending session before entering a transaction context')
        self._scope_active = True
        self._scope_failed = False
        try:
            try:
                yield self
                if self._failed or self._scope_failed:
                    raise TransactionStateError('Session transaction rolled back after a failed operation')
                self._commit_pending()
            except BaseException as error:
                try:
                    self._finish(False)
                except BaseException as cleanup_error:
                    error.add_note(f'Scope rollback failed: {type(cleanup_error).__name__}')
                    raise error from cleanup_error
                raise
        finally:
            self._scope_active = False
            self._scope_failed = False

    def close(self) -> None:
        self._runtime._check_owner()
        if self._closed:
            return
        self._check_manual_completion()
        error: BaseException | None = None
        self._executing = True
        try:
            try:
                self._finish(False)
            except BaseException as failure:
                error = failure
            self._executing = True
            try:
                self._discard_connection()
            except BaseException as failure:
                if error is None:
                    error = failure
                else:
                    error.add_note(f'Connection cleanup also failed: {type(failure).__name__}')
        finally:
            self._runtime.close()
            self._executing = False
            self._closed = True
        if error is not None:
            raise error
