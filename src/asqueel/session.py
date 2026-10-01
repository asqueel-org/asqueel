"""Lazy synchronous application session retaining its physical connection."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from .contracts import CompiledQuery, QueryResult
from .drivers.base import SyncDriver
from .environment import SqlEnvironment
from threading import current_thread

from .errors import DatabaseClosedError, TransactionStateError


class DeferredCommitError(RuntimeError):
    """One or more errors deliberately queued for the commit boundary."""


class Session:
    """One named unit of work; commit/rollback retain the connection for reuse.

    SQL execution errors immediately roll back, as in legacy GnrSqlDb.execute.
    Python domain failures remain rollback-only until explicitly cleared.
    Completion is always explicit.
    """

    def __init__(self, driver: SyncDriver, conninfo: str = '', *,
                 connect_kwargs: dict[str, Any] | None = None,
                 environment: SqlEnvironment | None = None,
                 connection_name: str | None = None):
        self.environment = environment if environment is not None else SqlEnvironment()
        self.driver = driver
        self.conninfo = conninfo
        self.connect_kwargs = dict(connect_kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self._owner = current_thread()
        self._connection: Any = None
        self._pending = False
        self._committing = False
        self._completion_failed = False
        self._connection_name = connection_name
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

    def _check_owner(self) -> None:
        if current_thread() is not self._owner:
            raise TransactionStateError('Connection operations must run on the constructing thread')

    def _check_open(self) -> None:
        self._check_owner()
        if self._closed:
            raise DatabaseClosedError('Connection is closed')

    def _check_available(self) -> None:
        self._check_open()
        if self._executing:
            raise TransactionStateError('Session is already executing an operation')

    def _check_manual_completion(self) -> None:
        self._check_available()
        if self._committing:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')

    def _check_usable(self) -> None:
        self._check_available()
        if self._failed or self._completion_failed:
            raise TransactionStateError('Session is rollback-only; call rollback before reuse')

    def execute(self, query: CompiledQuery) -> QueryResult:
        self._check_usable()
        self.driver.validate(query)
        if query.environment is not None:
            query.environment.validate(self.environment.snapshot())
        self._execution_count += 1
        self._executing = True
        self._execution_error = None
        try:
            if self._connection is None:
                self._connection = self.driver.connect(
                    self.conninfo, **self.connect_kwargs)
            self._pending = True
            self.outcome = 'active'
            return self.driver.execute(self._connection, query)
        except BaseException as error:
            self._execution_error = error
            self._completion_failed = self._committing
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
            self.driver.close(connection)

    def _finish(self, commit: bool) -> None:
        if not self._pending:
            if self.outcome != 'unknown':
                self._failed = False
            if not commit:
                self._clear_deferred()
            return
        self._executing = True
        try:
            operation = self.driver.commit if commit else self.driver.rollback
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
                    # Propagate without consuming callbacks that were not reached.
                    # The application owns recovery; rollback/close clears queues.
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

    def close(self) -> None:
        self._check_owner()
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
            self._executing = False
            self._closed = True
        if error is not None:
            raise error
