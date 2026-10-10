"""Shared execution path, thread-local named connections and explicit completion."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Thread, current_thread, local
from typing import Any, TypedDict
from uuid import uuid4

from .contracts import CompiledQuery, QueryResult, UnsupportedFeatureError
from .environment import ApplicationEnvironment
from .drivers.base import SyncDriver
from .errors import DatabaseClosedError, DeferredCommitError, TransactionStateError
from .triggers import TriggerStack


class _ConnectionState(TypedDict):
    """Private data in the DB's named-connection dictionary; no independent API."""
    owner: Thread
    connection: Any
    pending: bool
    committing: bool
    completion_failed: bool
    connection_name: str
    failed: bool
    executing: bool
    closed: bool
    execution_error: BaseException | None
    execution_count: int
    deferred: dict[str, dict[str, dict[tuple[int, str], tuple[Any, tuple, dict]]]]
    pending_exceptions: list[BaseException]
    outcome: str


class _ThreadState(local):
    def __init__(self) -> None:
        self.connections: dict[str, _ConnectionState] = {}
        self.write_depth = 0
        self.trigger_stack = TriggerStack()
        self.closed = False
        self.acquired = False


class Database:
    """Shared execution service. Statements remain pending until commit/rollback.

    Handles can be shared between threads; each worker releases its own named
    connections. Use tempEnv for context selection, never automatic completion.
    """

    def __init__(self, conninfo='', *, driver: SyncDriver, connect_kwargs=None, environment=None):
        self._ready = True
        self._thread_state = _ThreadState()
        self.driver = driver
        self.conninfo = conninfo
        self.connect_kwargs = dict(connect_kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self.environment = environment if environment is not None else ApplicationEnvironment()

    def _connection_settings(self):
        return self.conninfo, self.connect_kwargs

    def _check_open(self) -> None:
        if not self._ready:
            raise TransactionStateError('Database object graph is not ready')
        if self._closed:
            raise DatabaseClosedError('Database is closed')

    @property
    def _connections(self) -> dict[str, _ConnectionState]:
        connections: dict[str, _ConnectionState] = self._thread_state.connections
        return connections

    @property
    def _trigger_stack(self):
        return self._thread_state.trigger_stack

    @property
    def _write_depth(self):
        return self._thread_state.write_depth

    @_write_depth.setter
    def _write_depth(self, value):
        self._thread_state.write_depth = value

    @property
    def _closed(self):
        return self._thread_state.closed

    @_closed.setter
    def _closed(self, value):
        self._thread_state.closed = value

    @property
    def currentConnectionName(self) -> str:
        self._check_open()
        name = self.environment.currentEnv.get('connectionName') or '_main_connection'
        if not isinstance(name, str):
            raise TypeError('connectionName must be a string')
        return name

    def usingMainConnection(self) -> bool:
        return self.currentConnectionName == '_main_connection'

    def _check_store(self) -> None:
        store = self.environment.currentEnv.get('storename')
        if store and store != '_main_db':
            raise UnsupportedFeatureError('Database stores are not implemented in this profile')

    @property
    def _connection_state(self) -> _ConnectionState:
        self._check_open()
        self._check_store()
        name = self.currentConnectionName
        if name not in self._connections:
            self._connections[name] = dict(
                owner=current_thread(), connection=None, pending=False,
                committing=False, completion_failed=False, connection_name=name,
                failed=False, executing=False, closed=False, execution_error=None,
                execution_count=0, deferred={'before': {}, 'after': {}},
                pending_exceptions=[], outcome='not_started',
            )
        return self._connections[name]

    @property
    def current_env(self):
        self._check_open()
        return self.environment.current_env

    @property
    def currentEnv(self):
        self._check_open()
        return self.environment.currentEnv

    @currentEnv.setter
    def currentEnv(self, values):
        self._check_open()
        self.environment.currentEnv = values

    def updateEnv(self, _excludeNoneValues=False, **values):
        self.currentEnv.update({key: value for key, value in values.items()
                                if not _excludeNoneValues or value is not None})

    def clearCurrentEnv(self):
        self.currentEnv = {}

    def acquire(self):
        """Take this database for the current call and return it.

        The first take on a thread clears ``currentEnv``, so a call never sees
        the context of the previous call on the same thread; ``closeConnection``
        ends the take, and the next one belongs to the next call.
        """
        self._check_open()
        if not self._thread_state.acquired:
            self.clearCurrentEnv()
            self._thread_state.acquired = True
        return self

    @property
    def workdate(self):
        self._check_open()
        return self.environment.workdate

    @workdate.setter
    def workdate(self, value):
        self.currentEnv['workdate'] = value

    @property
    def locale(self):
        self._check_open()
        return self.environment.locale

    @locale.setter
    def locale(self, value):
        self.currentEnv['locale'] = value

    @contextmanager
    def temp_env(self, **values: Any):
        self._check_open()
        with self.environment.temp_env(**values):
            yield self

    def tempEnv(self, **values: Any):
        return self.temp_env(**values)

    @property
    def outcome(self) -> str:
        """Most recent named connection transaction outcome, including uncertain commit."""
        name = self.environment.currentEnv.get('connectionName') or '_main_connection'
        state = self._connections.get(name)
        return state['outcome'] if state is not None else 'not_started'

    def execute(self, query: CompiledQuery | str, sqlargs=None) -> QueryResult:
        """Execute a compiled statement in this DB's shared unit of work."""
        self._check_open()
        if isinstance(query, str):
            return self._execute_on_connection(self._connection_state, self._prepare_sql(query, sqlargs))
        elif sqlargs is not None:
            raise TypeError('Parameters are already part of a CompiledQuery')
        return self._execute_on_connection(self._connection_state, query)

    def _prepare_sql(self, sql, sqlargs) -> CompiledQuery:
        query: CompiledQuery = self.driver.prepare_sql(sql, sqlargs, self.environment.snapshot())
        return query

    @property
    def currentTrigger(self):
        """Current write operation, including its causal parent and level."""
        self._check_open()
        return self._trigger_stack.parentItem

    @contextmanager
    def _trigger_operation(self, event, table, record=None, old_record=None):
        self._check_open()
        with self._trigger_stack.operation(
                event, table.fullname, record=record, old_record=old_record) as item:
            yield item

    def deferToCommit(self, callback, *args, **kwargs):
        """Run a callback before committing the selected named connection."""
        self._check_open()
        return self._defer(self._connection_state, 'before', callback, *args, **kwargs)

    def deferAfterCommit(self, callback, *args, **kwargs):
        """Run a callback after committing the selected named connection."""
        self._check_open()
        return self._defer(self._connection_state, 'after', callback, *args, **kwargs)

    def deferredRaise(self, exception):
        """Make the selected named connection fail at its next commit."""
        self._check_open()
        self._deferred_raise(self._connection_state, exception)

    def _check_boundary(self) -> None:
        self._check_open()
        if self._write_depth:
            raise TransactionStateError('Cannot finish a transaction inside a table write or hook')

    def commit(self) -> None:
        self._check_boundary()
        self._commit_connection(self._connection_state)

    def rollback(self) -> None:
        self._check_boundary()
        self._rollback_connection(self._connection_state)

    @contextmanager
    def _write_operation(self):
        self._check_open()
        state = self._connection_state
        self._check_connection_usable(state)
        execution_count = state['execution_count']
        self._write_depth += 1
        try:
            yield
        except BaseException as error:
            # Only an execution error from this operation's own connection has
            # already rolled back its work. Another connection's rollback cannot
            # repair this incomplete write; neither can an older SQL failure.
            if not (state['execution_count'] != execution_count
                    and state['execution_error'] is error):
                self._mark_connection_failed(state)
            raise
        finally:
            self._write_depth -= 1

    def closeConnection(self) -> None:
        """Release the current thread's named connections, keeping it usable."""
        self._check_boundary()
        for state in self._connections.values():
            self._check_connection_completion(state)
        try:
            self._close_connections()
        finally:
            self._connections.clear()
            self._thread_state.acquired = False

    def _close_connections(self) -> None:
        error = None
        for state in self._connections.values():
            try:
                self._close_connection(state)
            except BaseException as failure:
                if error is None:
                    error = failure
                else:
                    error.add_note(f'Another named connection cleanup failed: {type(failure).__name__}')
        if error is not None:
            raise error

    def close(self) -> None:
        """Close this thread's DB state; other threads remain usable."""
        if self._write_depth:
            raise TransactionStateError('Cannot close the database inside a table write or hook')
        if self._closed:
            return
        # Preflight all scopes before closing anything; then clean every named
        # connection even when one driver rollback/close fails.
        for state in self._connections.values():
            self._check_connection_completion(state)
        try:
            self._close_connections()
        finally:
            self._closed = True

    def _defer(self, state: _ConnectionState, queue: str, callback, *args, **kwargs):
        self._check_connection_usable(state)
        block = kwargs.pop('_deferredBlock', None) or '_base_'
        deferred_id = kwargs.pop('_deferredId', None)
        if not deferred_id:
            deferred_id = uuid4().hex
        entries = state['deferred'][queue].setdefault(block, {})
        key = (id(callback), str(deferred_id))
        if key not in entries:
            entries[key] = (callback, args, kwargs)
            return kwargs
        return entries[key][2]

    def _deferred_raise(self, state: _ConnectionState, exception: BaseException) -> None:
        self._check_connection_usable(state)
        if not isinstance(exception, BaseException):
            raise TypeError('deferred_raise requires an exception instance')
        state['pending_exceptions'].append(exception)

    def _invoke_deferred(self, state: _ConnectionState, queue: str) -> None:
        context: dict[str, Any] = {'onCommittingStep': True}
        if state['connection_name'] is not None:
            context['connectionName'] = state['connection_name']
        with self.environment.temp_env(**context):
            self._drain_deferred(state, queue)

    def _drain_deferred(self, state: _ConnectionState, queue: str) -> None:
        blocks = state['deferred'][queue]
        while blocks:
            block_name = sorted(blocks)[0]
            entries = blocks[block_name]
            while entries:
                key = next(iter(entries))
                callback, args, kwargs = entries.pop(key)
                callback(*args, **kwargs)
                self._check_connection_usable(state)
                if not getattr(callback, 'deferredCommitRecursion', False):
                    entries.pop(key, None)
            blocks.pop(block_name, None)

    def _clear_deferred(self, state: _ConnectionState) -> None:
        state['deferred']['before'].clear()
        state['deferred']['after'].clear()
        state['pending_exceptions'].clear()

    def _check_connection_owner(self, state: _ConnectionState) -> None:
        if current_thread() is not state['owner']:
            raise TransactionStateError('Connection operations must run on the constructing thread')

    def _check_connection_open(self, state: _ConnectionState) -> None:
        self._check_connection_owner(state)
        if state['closed']:
            raise DatabaseClosedError('Connection is closed')

    def _check_connection_available(self, state: _ConnectionState) -> None:
        self._check_connection_open(state)
        if state['executing']:
            raise TransactionStateError('Connection is already executing an operation')

    def _check_connection_completion(self, state: _ConnectionState) -> None:
        self._check_connection_available(state)
        if state['committing']:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')

    def _check_connection_usable(self, state: _ConnectionState) -> None:
        self._check_connection_available(state)
        if state['failed'] or state['completion_failed']:
            raise TransactionStateError('Connection is rollback-only; call rollback before reuse')

    def _execute_on_connection(self, state: _ConnectionState, query: CompiledQuery) -> QueryResult:
        self._check_connection_usable(state)
        self.driver.validate(query)
        if query.environment is not None:
            query.environment.validate(self.environment.snapshot())
        state['execution_count'] += 1
        state['executing'] = True
        state['execution_error'] = None
        try:
            if state['connection'] is None:
                conninfo, connect_kwargs = self._connection_settings()
                if connect_kwargs.get('autocommit'):
                    raise ValueError('autocommit is incompatible with explicit transactions')
                state['connection'] = self.driver.connect(
                    conninfo, **connect_kwargs)
            state['pending'] = True
            state['outcome'] = 'active'
            return self.driver.execute(state['connection'], query)
        except BaseException as error:
            state['execution_error'] = error
            state['completion_failed'] = state['committing']
            try:
                self._finish(state, False)
            except BaseException as cleanup_error:
                # The original execution error must remain catchable by callers.
                error.add_note(f'Automatic rollback failed: {type(cleanup_error).__name__}')
                raise error from cleanup_error
            raise
        finally:
            state['executing'] = False

    def _mark_connection_failed(self, state: _ConnectionState) -> None:
        """Mark a failed domain operation even when no SQL has run yet."""
        self._check_connection_open(state)
        state['failed'] = True

    def _discard_connection(self, state: _ConnectionState) -> None:
        connection, state['connection'] = state['connection'], None
        if connection is not None:
            self.driver.close(connection)

    def _finish(self, state: _ConnectionState, commit: bool) -> None:
        if not state['pending']:
            if state['outcome'] != 'unknown':
                state['failed'] = False
            if not commit:
                self._clear_deferred(state)
            return
        state['executing'] = True
        try:
            operation = self.driver.commit if commit else self.driver.rollback
            operation(state['connection'])
            state['outcome'] = 'committed' if commit else 'rolled_back'
            state['failed'] = False
        except BaseException as error:
            state['outcome'] = 'unknown'
            state['failed'] = True
            try:
                self._discard_connection(state)
            except BaseException as close_error:
                error.add_note(f'Connection cleanup also failed: {type(close_error).__name__}')
            raise
        finally:
            state['pending'] = False
            state['executing'] = False
            if not commit or state['outcome'] == 'unknown':
                self._clear_deferred(state)

    def _commit_pending(self, state: _ConnectionState) -> None:
        if state['committing']:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')
        state['committing'] = True
        state['completion_failed'] = False
        try:
            while state['pending']:
                try:
                    self._invoke_deferred(state, 'before')
                    self._check_connection_usable(state)
                    if state['pending_exceptions']:
                        messages = '\n'.join(str(error) for error in state['pending_exceptions'])
                        raise DeferredCommitError(messages)
                except BaseException:
                    state['failed'] = True
                    raise
                state['pending_exceptions'].clear()
                self._finish(state, True)
                try:
                    self._invoke_deferred(state, 'after')
                except BaseException:
                    # The preceding transaction is committed and cannot be undone.
                    # A callback may have opened a new transaction: retain its
                    # failure until the caller rolls it back.
                    if state['pending']:
                        state['failed'] = True
                    # Propagate without consuming callbacks that were not reached.
                    # The application owns recovery; rollback/close clears queues.
                    raise
        finally:
            state['committing'] = False
            state['completion_failed'] = False

    def _commit_connection(self, state: _ConnectionState) -> None:
        self._check_connection_completion(state)
        if state['failed']:
            raise TransactionStateError('Connection is rollback-only; call rollback before reuse')
        self._commit_pending(state)

    def _rollback_connection(self, state: _ConnectionState) -> None:
        self._check_connection_completion(state)
        self._finish(state, False)
        state['failed'] = False

    def _close_connection(self, state: _ConnectionState) -> None:
        self._check_connection_owner(state)
        if state['closed']:
            return
        self._check_connection_completion(state)
        error: BaseException | None = None
        state['executing'] = True
        try:
            try:
                self._finish(state, False)
            except BaseException as failure:
                error = failure
            state['executing'] = True
            try:
                self._discard_connection(state)
            except BaseException as failure:
                if error is None:
                    error = failure
                else:
                    error.add_note(f'Connection cleanup also failed: {type(failure).__name__}')
        finally:
            state['executing'] = False
            state['closed'] = True
        if error is not None:
            raise error

    def __enter__(self) -> Database:
        self._check_open()
        return self

    def __exit__(self, exc_type: Any, error: Any, traceback: Any) -> None:
        try:
            self.close()
        except BaseException as cleanup_error:
            if error is None:
                raise
            error.add_note(f'Database cleanup failed: {type(cleanup_error).__name__}')
            raise error from cleanup_error


class PostgresDatabase(Database):
    """Driver-selecting facade using the shared, explicitly completed runtime."""

    def __init__(self, conninfo='', *, connect_kwargs=None, driver=None, environment=None):
        from .drivers.psycopg import PsycopgDriver
        driver = driver if driver is not None else PsycopgDriver()
        if (driver.dialect, driver.binding) != ('postgresql', 'psycopg_named'):
            raise ValueError('PostgresDatabase requires the postgresql/psycopg_named driver profile')
        super().__init__(conninfo, driver=driver, connect_kwargs=connect_kwargs,
                         environment=environment)
