"""Shared execution path, thread-local named connections and explicit completion."""
from __future__ import annotations

from contextlib import contextmanager
from threading import local
from typing import Any

from .contracts import CompiledQuery, QueryResult, UnsupportedFeatureError
from .environment import ApplicationEnvironment
from .errors import DatabaseClosedError, TransactionStateError
from .session import Session
from .triggers import TriggerStack


class _ThreadState(local):
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.write_depth = 0
        self.trigger_stack = TriggerStack()
        self.closed = False


class Database:
    """Shared execution service. Statements remain pending until commit/rollback.

    Handles can be shared between threads; each worker releases its own named
    connections. Use tempEnv for context selection, never automatic completion.
    """

    def __init__(self, conninfo='', *, driver, connect_kwargs=None, environment=None):
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
    def _sessions(self) -> dict[str, Session]:
        sessions: dict[str, Session] = self._thread_state.sessions
        return sessions

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
    def _session(self) -> Session:
        self._check_open()
        self._check_store()
        name = self.currentConnectionName
        if name not in self._sessions:
            conninfo, connect_kwargs = self._connection_settings()
            self._sessions[name] = Session(
                driver=self.driver,
                conninfo=conninfo,
                connect_kwargs=connect_kwargs,
                environment=self.environment,
                connection_name=name,
            )
        return self._sessions[name]

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
        """Most recent session transaction outcome, including uncertain commit."""
        name = self.environment.currentEnv.get('connectionName') or '_main_connection'
        session = self._sessions.get(name)
        return session.outcome if session is not None else 'not_started'

    def execute(self, query: CompiledQuery | str, sqlargs=None) -> QueryResult:
        """Execute a compiled statement in this DB's shared unit of work."""
        self._check_open()
        if isinstance(query, str):
            return self._session.execute(self._prepare_sql(query, sqlargs))
        elif sqlargs is not None:
            raise TypeError('Parameters are already part of a CompiledQuery')
        return self._session.execute(query)

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
        return self._session.defer_to_commit(callback, *args, **kwargs)

    def deferAfterCommit(self, callback, *args, **kwargs):
        """Run a callback after committing the selected named connection."""
        self._check_open()
        return self._session.defer_after_commit(callback, *args, **kwargs)

    def deferredRaise(self, exception):
        """Make the selected named connection fail at its next commit."""
        self._check_open()
        self._session.deferred_raise(exception)

    def _check_boundary(self) -> None:
        self._check_open()
        if self._write_depth:
            raise TransactionStateError('Cannot finish a transaction inside a table write or hook')

    def commit(self) -> None:
        self._check_boundary()
        self._session.commit()

    def rollback(self) -> None:
        self._check_boundary()
        self._session.rollback()

    @contextmanager
    def _write_operation(self):
        self._check_open()
        session = self._session
        session._check_usable()
        execution_count = session._execution_count
        self._write_depth += 1
        try:
            yield
        except BaseException as error:
            # Only an execution error from this operation's own session has
            # already rolled back its work. Another session's rollback cannot
            # repair this incomplete write; neither can an older SQL failure.
            if not (session._execution_count != execution_count
                    and session._execution_error is error):
                session.mark_failed()
            raise
        finally:
            self._write_depth -= 1

    def closeConnection(self) -> None:
        """Release the current thread's named connections, keeping it usable."""
        self._check_boundary()
        for session in self._sessions.values():
            session._check_manual_completion()
        try:
            self._close_sessions()
        finally:
            self._sessions.clear()

    def _close_sessions(self) -> None:
        error = None
        for session in self._sessions.values():
            try:
                session.close()
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
        for session in self._sessions.values():
            session._check_manual_completion()
        try:
            self._close_sessions()
        finally:
            self._closed = True

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
