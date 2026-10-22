"""Shared execution path, thread-local named connections and explicit completion."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from importlib import import_module
import re
from threading import Thread, current_thread, local
from typing import Any, Iterator, TypedDict
from uuid import uuid4
from weakref import WeakSet

from genro_bag import Bag
from genro_toolbox import NamedList

from .contracts import CompiledQuery, UnsupportedFeatureError, not_available, refused_property
from .environment import ApplicationEnvironment, environment_arguments
from .errors import DeferredCommitError, TransactionStateError
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
    execution_error: BaseException | None
    execution_count: int
    write_depth: int
    cursors: WeakSet[SqlCursor]


class _ThreadState(local):
    def __init__(self) -> None:
        self.connections: dict[str, _ConnectionState] = {}
        self.trigger_stack = TriggerStack()
        self.session_open = False


class Database:
    """Shared execution service. Statements remain pending until commit/rollback.

    Handles can be shared between threads; each worker releases its own named
    connections. Use tempEnv for context selection, never automatic completion.
    """

    @property
    def tableMixin(self):
        raise not_available('tableMixin')

    @property
    def packageMixin(self):
        raise not_available('packageMixin')

    query = refused_property('db.query')
    whereTranslator = refused_property('db.whereTranslator')


    def __init__(self, conninfo='', *, implementation='sqlite', connect_kwargs=None, environment=None):
        self._ready = True
        self._thread_state = _ThreadState()
        # Legacy adapter loading: 'name' or 'name:module'; the module exposes SqlDbAdapter.
        if ':' in implementation:
            implementation, module = implementation.split(':')
        else:
            module = f'asqueel.adapters.{implementation}'
        self.implementation = implementation
        self.adapters: dict[str, Any] = {implementation: import_module(module).SqlDbAdapter(self)}
        self.conninfo = conninfo
        self.connect_kwargs = dict(connect_kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self.environment = environment if environment is not None else ApplicationEnvironment()

    @property
    def adapter(self):
        """The adapter of the current implementation; ``currentImplementation`` overrides it."""
        implementation = self.environment.currentEnv.get('currentImplementation') or self.implementation
        if implementation not in self.adapters:
            self.adapters[implementation] = import_module(f'asqueel.adapters.{implementation}').SqlDbAdapter(self)
        return self.adapters[implementation]

    def _connection_settings(self):
        return self.conninfo, self.connect_kwargs

    def _check_open(self) -> None:
        if not self._ready:
            raise TransactionStateError('Database object graph is not ready')

    @property
    def _connections(self) -> dict[str, _ConnectionState]:
        connections: dict[str, _ConnectionState] = self._thread_state.connections
        return connections

    @property
    def _trigger_stack(self):
        return self._thread_state.trigger_stack

    @property
    def _write_depth(self):
        """Table writes in progress on the selected named connection."""
        return self._connection_state['write_depth']

    def _writing(self) -> bool:
        return any(state['write_depth'] for state in self._connections.values())

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
            raise UnsupportedFeatureError(f'environment key storename={store!r}: database stores are not available in this release')

    @property
    def _connection_state(self) -> _ConnectionState:
        self._check_open()
        self._check_store()
        name = self.currentConnectionName
        if name not in self._connections:
            self._connections[name] = dict(
                owner=current_thread(), connection=None, pending=False,
                committing=False, completion_failed=False, connection_name=name,
                failed=False, executing=False, execution_error=None,
                execution_count=0, write_depth=0, cursors=WeakSet(),
            )
        return self._connections[name]

    @property
    def currentEnv(self):
        self._check_open()
        return self.environment.currentEnv

    @currentEnv.setter
    def currentEnv(self, values):
        self._check_open()
        self.environment.currentEnv = values

    @property
    def currentUser(self):
        return self.currentEnv.get('user')

    def updateEnv(self, _excludeNoneValues=False, **values):
        self.currentEnv.update({key: value for key, value in values.items()
                                if not _excludeNoneValues or value is not None})

    def clearCurrentEnv(self):
        self.currentEnv = {}

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
    def tempEnv(self, **values: Any):
        self._check_open()
        with self.environment.tempEnv(**values):
            yield self

    def execute(self, sql: CompiledQuery | str, sqlargs=None, cursor=None, cursorname=None,
                autocommit=False, dbtable=None, storename=None, _adaptArguments=True) -> SqlCursor:
        """Execute a statement in this DB's unit of work and return its open cursor, as legacy.

        ``cursorname`` asks for a server-side cursor (``'*'`` generates the name);
        ``autocommit`` commits after the statement; ``dbtable`` only names the table.
        """
        self._check_open()
        for name, refused in (('storename', storename not in (None, False)), ('cursor', cursor is not None),
                              ('_adaptArguments', not _adaptArguments)):
            if refused:
                raise UnsupportedFeatureError(f'{name} is not available in this release')
        if isinstance(sql, str):
            sql = self._prepare_sql(sql, sqlargs)
        elif sqlargs is not None:
            raise TypeError('Parameters are already part of a CompiledQuery')
        if cursorname == '*':
            cursorname = 'c' + uuid4().hex
        result = self._execute_on_connection(self._connection_state, sql, cursorname=cursorname)
        if autocommit:
            self.commit()
        return result

    def executemany(self, query: CompiledQuery, params_seq) -> SqlCursor:
        """Execute one compiled statement once per parameter mapping, as DB-API executemany."""
        self._check_open()
        return self._execute_on_connection(self._connection_state, query, many=tuple(params_seq))

    def cursor(self, query: CompiledQuery, cursorname=None) -> SqlCursor:
        """Execute a compiled SELECT and return its open cursor; ``cursorname`` asks for a server-side cursor."""
        return self.execute(query, cursorname=cursorname)

    def _prepare_sql(self, sql, sqlargs) -> CompiledQuery:
        query: CompiledQuery = self.adapter.prepare_sql(sql, sqlargs, self.environment.snapshot())
        return query

    @property
    def currentTrigger(self):
        """Current write operation; ``parent`` is the operation that caused it."""
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
        return self._defer(self._connection_state, 'to_commit_defer_calls', callback, *args, **kwargs)

    def deferAfterCommit(self, callback, *args, **kwargs):
        """Run a callback after committing the selected named connection."""
        self._check_open()
        return self._defer(self._connection_state, 'after_commit_defer_calls', callback, *args, **kwargs)

    def deferredRaise(self, exception):
        """Make the selected named connection fail at its next commit."""
        self._check_open()
        self._deferred_raise(self._connection_state, exception)

    def _check_boundary(self) -> None:
        self._check_open()
        if self._write_depth:
            raise TransactionStateError('Cannot finish the transaction of a table write or hook in progress')

    def commit(self) -> None:
        self._check_boundary()
        self._commit_connection(self._connection_state)
        self.onDbCommitted()

    def onDbCommitted(self) -> None:
        """Called once at the end of every commit, as legacy; subclasses override it."""

    def setLocale(self) -> None:
        """Hand the environment locale to the adapter, as legacy."""
        locale = self.currentEnv.get('locale')
        if locale:
            self.adapter.setLocale(locale)

    def setConstraintsDeferred(self) -> None:
        """Defer the deferrable constraints until the commit of the current transaction."""
        self.adapter.setConstraintsDeferred()

    def analyze(self) -> None:
        """Update the planner statistics, in the current transaction."""
        self.adapter.analyze()

    def vacuum(self, table: str = '', full: bool = False) -> None:
        """Reclaim storage of the database or of ``table`` (its SQL name), on a separate connection.

        The work pending on this thread would hold the locks the separate connection waits for.
        """
        self._check_open()
        if any(state['pending'] for state in self._connections.values()):
            raise TransactionStateError('vacuum requires no pending work on this thread; commit or rollback first')
        self.adapter.vacuum(table=table, full=full)

    def rollback(self) -> None:
        self._check_boundary()
        self._rollback_connection(self._connection_state)

    @contextmanager
    def _write_operation(self):
        self._check_open()
        state = self._connection_state
        self._check_connection_usable(state)
        execution_count = state['execution_count']
        state['write_depth'] += 1
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
            state['write_depth'] -= 1

    def closeConnection(self) -> None:
        """Roll back and close every named connection of the current thread, as legacy.

        The database stays usable: the next statement opens a new connection.
        """
        self._check_open()
        if self._writing():
            raise TransactionStateError('Cannot close connections inside a table write or hook')
        for state in self._connections.values():
            self._check_connection_completion(state)
        try:
            self._close_connections()
        finally:
            self._connections.clear()

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

    def _deferred_key(self, state: _ConnectionState, queue: str) -> str:
        """The currentEnv key of a deferred queue or of the pending exceptions of ``state``.

        Legacy keys the queues ``f'{queue}_{connectionKey()}'`` and keeps one
        global ``_pendingExceptions``; here the pending exceptions are per named
        connection too.
        """
        return f"{queue}__main_db_{state['connection_name']}"

    def _defer(self, state: _ConnectionState, queue: str, callback, *args, **kwargs):
        self._check_connection_usable(state)
        block = kwargs.pop('_deferredBlock', None) or '_base_'
        deferred_id = kwargs.pop('_deferredId', None)
        if not deferred_id:
            deferred_id = uuid4().hex
        blocks = self.environment.currentEnv.setdefault(self._deferred_key(state, queue), Bag())
        if block not in blocks:
            blocks[block] = Bag()
        entries = blocks[block]
        key = f'{id(callback)}/{deferred_id}'
        if key not in entries:
            entries[key] = (callback, args, kwargs)
            return kwargs
        return entries[key][2]

    def _deferred_raise(self, state: _ConnectionState, exception: BaseException) -> None:
        self._check_connection_usable(state)
        if not isinstance(exception, BaseException):
            raise TypeError('deferred_raise requires an exception instance')
        self.environment.currentEnv.setdefault(self._deferred_key(state, '_pendingExceptions'), []).append(exception)

    def _invoke_deferred(self, state: _ConnectionState, queue: str) -> None:
        context: dict[str, Any] = {'onCommittingStep': True}
        if state['connection_name'] is not None:
            context['connectionName'] = state['connection_name']
        with self.environment.tempEnv(**context):
            self._drain_deferred(state, queue)

    def _drain_deferred(self, state: _ConnectionState, queue: str) -> None:
        blocks = self.environment.currentEnv.get(self._deferred_key(state, queue))
        while blocks:
            # GenroPy Bag.sort('#k:a'): labels in lowercase, stable on ties.
            block_name = min(blocks.keys(), key=str.lower)
            entries = blocks[block_name]
            while entries:
                key = next(iter(entries.keys()))
                callback, args, kwargs = entries.pop(key)
                callback(*args, **kwargs)
                self._check_connection_usable(state)
                if not getattr(callback, 'deferredCommitRecursion', False):
                    entries.pop(key, None)
            blocks.pop(block_name, None)

    def _pop_transaction_key(self, key: str) -> Any:
        """Pop a deferred queue or the pending exceptions from currentEnv.

        The read-only snapshot of a ``SqlEnvironment`` holds none of them.
        """
        current = self.environment.currentEnv
        return current.pop(key, None) if isinstance(current, dict) else None

    def _clear_deferred(self, state: _ConnectionState) -> None:
        self._pop_transaction_key(self._deferred_key(state, 'to_commit_defer_calls'))
        self._pop_transaction_key(self._deferred_key(state, 'after_commit_defer_calls'))
        self._pop_transaction_key(self._deferred_key(state, '_pendingExceptions'))

    def _check_connection_owner(self, state: _ConnectionState) -> None:
        if current_thread() is not state['owner']:
            raise TransactionStateError('Connection operations must run on the constructing thread')

    def _check_connection_available(self, state: _ConnectionState) -> None:
        self._check_connection_owner(state)
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

    def _check_environment_keys(self) -> None:
        """Refuse the legacy environment keys whose effect this release does not have."""
        for key in self.environment.currentEnv:
            if key in ('sql_comment', 'sql_details') or re.fullmatch(r'env_\w+_condition_\w+', key):
                raise UnsupportedFeatureError(f'environment key {key!r} is not available in this release')

    def _execute_on_connection(self, state: _ConnectionState, query: CompiledQuery, many=None,
                               cursorname=None) -> SqlCursor:
        self._check_connection_usable(state)
        self._check_environment_keys()
        adapter = self.adapter
        adapter.validate(query)
        if query.environment_keys:
            query = replace(query, params={**query.params, **environment_arguments(
                query.environment_keys, self.environment.snapshot())})
        state['execution_count'] += 1
        state['executing'] = True
        state['execution_error'] = None
        try:
            if state['connection'] is None:
                conninfo, connect_kwargs = self._connection_settings()
                if connect_kwargs.get('autocommit'):
                    raise ValueError('autocommit is incompatible with explicit transactions')
                state['connection'] = adapter.connect(conninfo, **connect_kwargs)
            state['pending'] = True
            cursor = (adapter.executemany(state['connection'], query, many) if many is not None
                      else adapter.execute(state['connection'], query, cursorname))
            result = SqlCursor(self, state, cursor, query.columns)
            state['cursors'].add(result)
            return result
        except BaseException as error:
            self._execution_failed(state, error)
            raise
        finally:
            state['executing'] = False

    def _execution_failed(self, state: _ConnectionState, error: BaseException) -> None:
        """The automatic rollback after an error raised by execute or by a fetch."""
        state['execution_error'] = error
        state['completion_failed'] = state['committing']
        try:
            self._finish(state, False)
        except BaseException as cleanup_error:
            # The original execution error must remain catchable by callers.
            error.add_note(f'Automatic rollback failed: {type(cleanup_error).__name__}')
            raise error from cleanup_error

    def _mark_connection_failed(self, state: _ConnectionState) -> None:
        """Mark a failed domain operation even when no SQL has run yet."""
        self._check_connection_owner(state)
        state['failed'] = True

    def _discard_connection(self, state: _ConnectionState) -> None:
        # A cursor still referenced keeps its statement alive; on SQLite it keeps the file locked.
        # The record is weak: a cursor nobody references is released by the driver.
        for cursor in tuple(state['cursors']):
            cursor.close()
        connection, state['connection'] = state['connection'], None
        if connection is not None:
            self.adapter.close(connection)

    def _finish(self, state: _ConnectionState, commit: bool) -> None:
        if not state['pending']:
            state['failed'] = False
            if not commit:
                self._clear_deferred(state)
            return
        state['executing'] = True
        uncertain = False
        try:
            operation = self.adapter.commit if commit else self.adapter.rollback
            operation(state['connection'])
            state['failed'] = False
        except BaseException as error:
            uncertain = True
            state['failed'] = True
            try:
                self._discard_connection(state)
            except BaseException as close_error:
                error.add_note(f'Connection cleanup also failed: {type(close_error).__name__}')
            raise
        finally:
            state['pending'] = False
            state['executing'] = False
            if not commit or uncertain:
                self._clear_deferred(state)

    def _commit_pending(self, state: _ConnectionState) -> None:
        if state['committing']:
            raise TransactionStateError('Cannot reenter transaction completion from a commit callback')
        state['committing'] = True
        state['completion_failed'] = False
        try:
            while state['pending']:
                try:
                    self._invoke_deferred(state, 'to_commit_defer_calls')
                    self._check_connection_usable(state)
                    pending_exceptions = self._pop_transaction_key(self._deferred_key(state, '_pendingExceptions'))
                    if pending_exceptions:
                        messages = '\n'.join(str(error) for error in pending_exceptions)
                        raise DeferredCommitError(messages)
                except BaseException:
                    state['failed'] = True
                    raise
                self._finish(state, True)
                try:
                    self._invoke_deferred(state, 'after_commit_defer_calls')
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
        if error is not None:
            raise error

class SqlCursor:
    """The open cursor returned by ``db.execute``: rows read by name, as the legacy dict cursor.

    A driver error raised by a fetch rolls the connection back, as one raised by execute.
    """

    def __init__(self, db: Database, state: _ConnectionState, cursor, columns=()):
        self._db = db
        self._state = state
        self._connection = state['connection']
        self._cursor = cursor
        self._index: dict[str, int] = {}
        if cursor.description is None:
            if columns:
                raise ValueError('Compiled result columns supplied for a statement without a result set')
            return
        names = [column[0] for column in cursor.description]
        if len(set(names)) != len(names):
            raise ValueError('Result columns must have unique names; use explicit aliases')
        if columns and [column.name for column in columns] != names:
            raise ValueError('Compiled result columns do not match cursor column names and order')
        self._index = {name: position for position, name in enumerate(names)}

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self) -> int:
        rowcount: int = self._cursor.rowcount
        return rowcount

    @property
    def arraysize(self) -> int:
        arraysize: int = self._cursor.arraysize
        return arraysize

    @arraysize.setter
    def arraysize(self, value: int) -> None:
        self._cursor.arraysize = value

    def close(self) -> None:
        self._cursor.close()
        self._state['cursors'].discard(self)

    def _fetch(self, method, *args):
        try:
            return method(*args)
        except BaseException as error:
            # Roll back only the transaction this cursor belongs to, not one opened after it.
            state = self._state
            if (self._db._connections.get(state['connection_name']) is state
                    and state['connection'] is self._connection):
                self._db._execution_failed(state, error)
            raise

    def fetchone(self) -> NamedList | None:
        row = self._fetch(self._cursor.fetchone)
        return None if row is None else NamedList(self._index, row)

    def fetchmany(self, size: int | None = None) -> list[NamedList]:
        rows = self._fetch(self._cursor.fetchmany, *(() if size is None else (size,)))
        return [NamedList(self._index, row) for row in rows]

    def fetchall(self) -> list[NamedList]:
        return [NamedList(self._index, row) for row in self._fetch(self._cursor.fetchall)]

    def __iter__(self) -> Iterator[NamedList]:
        while (row := self.fetchone()) is not None:
            yield row


@contextmanager
def session(db: Database, **env: Any) -> Iterator[Database]:
    """The unit of work outside a request, as a legacy page request.

    Entry clears ``currentEnv`` and applies ``env``; exit, also when the body
    raises, calls ``closeConnection()``, which rolls back what was not
    committed. One session at a time per database and thread.
    """
    if not isinstance(db.environment, ApplicationEnvironment):
        raise TransactionStateError('session(db) requires a writable environment')
    if db._thread_state.session_open:
        raise TransactionStateError('a session is already open on this thread for this database')
    db.clearCurrentEnv()
    db.updateEnv(**env)
    db._thread_state.session_open = True
    try:
        yield db
    except BaseException as error:
        db._thread_state.session_open = False
        try:
            db.closeConnection()
        except BaseException as cleanup:
            error.add_note(f'Connection cleanup failed: {type(cleanup).__name__}')
        raise
    db._thread_state.session_open = False
    db.closeConnection()
