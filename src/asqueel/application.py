"""Application database: one configuration, live graph and named sessions."""
from __future__ import annotations

from contextlib import contextmanager
from types import MappingProxyType
from typing import Any

from .application_table import SqlTable
from .compiler import QueryCompiler
from .contracts import CompiledQuery, QueryResult, ResolvedModel, UnsupportedFeatureError
from .dialects.postgres import PostgresDialect
from .drivers.psycopg import PsycopgDriver
from .environment import ApplicationEnvironment, SqlEnvironment
from .runtime import DatabaseClosedError, TransactionStateError
from .session import Session
from .triggers import TriggerStack


class SqlDatabase:
    """A synchronous application database constructed from a configuration.

    Use ``AsqueelDb(recipe)`` for application code. A configuration's object
    renderer also supports this base class. Operations share a lazy session until explicit
    commit/rollback. Closing rolls back pending work; it never commits it.
    """

    def __init__(self, *, model: ResolvedModel, config, driver=None, dialect=None,
                 environment: SqlEnvironment | None = None):
        self._ready = False
        self._write_depth = 0
        self.config = config
        self.model = model
        from .configuration import connection_settings
        implementation, _, _ = connection_settings(config)
        if implementation != 'postgresql':
            raise UnsupportedFeatureError(f'Unsupported database implementation: {implementation!r}')
        self.driver = driver if driver is not None else PsycopgDriver()
        self.dialect = dialect if dialect is not None else PostgresDialect()
        if self.dialect.name != implementation:
            raise ValueError('Configured implementation does not match the data dialect')
        self.environment = ApplicationEnvironment(environment)
        self.compiler = QueryCompiler(model, self.dialect, self.driver, environment=self.environment)
        self._sessions: dict[str, Session] = {}
        self._trigger_stack = TriggerStack()
        self._closed = False
        from threading import get_ident
        self._owner = get_ident()
        self._tables: dict[str, SqlTable] = {}
        for descriptor in model.tables.values():
            table_class = descriptor.attributes.get('x_table_class', SqlTable)
            if not isinstance(table_class, type) or not issubclass(table_class, SqlTable):
                raise TypeError(f'{descriptor.key}: x_table_class must be a SqlTable subclass')
            self._tables[descriptor.key] = table_class(self, descriptor)
        self._ready = True

    def _check_open(self) -> None:
        if not self._ready:
            raise TransactionStateError('Database object graph is not ready')
        self._check_owner()
        if self._closed:
            raise DatabaseClosedError('Database is closed')

    def _check_owner(self) -> None:
        from threading import get_ident
        if get_ident() != self._owner:
            raise TransactionStateError('Database operations must run on the constructing thread')

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
            from .configuration import connection_settings
            implementation, conninfo, connect_kwargs = connection_settings(self.config)
            if implementation != self.dialect.name:
                raise ValueError('Configured implementation changed after database construction')
            self._sessions[name] = Session(
                driver=self.driver,
                conninfo=conninfo,
                connect_kwargs=connect_kwargs,
                environment=self.environment,
                connection_name=name,
            )
        return self._sessions[name]

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType(self._tables)

    def table(self, name: str) -> SqlTable:
        """Return the registered operational table, preserving object identity."""
        self._check_open()
        return self._tables[self.model.table(name).key]

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
        self._check_owner()
        name = self.environment.currentEnv.get('connectionName') or '_main_connection'
        session = self._sessions.get(name)
        return session.outcome if session is not None else 'not_started'

    def execute(self, query: CompiledQuery) -> QueryResult:
        """Execute a compiled statement in this DB's shared unit of work."""
        self._check_open()
        return self._session.execute(query)

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
    def transaction(self):
        """Group table operations atomically; enter with no pending transaction."""
        self._check_boundary()
        with self._session.transaction():
            yield self

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
        """Roll back and release all named connections, keeping the DB usable."""
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
        if self._write_depth:
            raise TransactionStateError('Cannot close the database inside a table write or hook')
        self._check_owner()
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

    def __enter__(self) -> SqlDatabase:
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


class AsqueelDb(SqlDatabase):
    """Load a configured database by registered name, recipe, folder or file.

    Construction validates the model without connecting. Use table(), commit(),
    rollback() and close() directly on this long-lived database object.
    """

    def __init__(self, source, *, parents=None, driver=None, dialect=None, environment=None):
        from .configuration import _effective_model_builder, _owned_handler
        from .model import resolve_model

        config = _owned_handler(source, parents)
        model = resolve_model(_effective_model_builder(config))
        super().__init__(model=model, config=config, driver=driver,
                         dialect=dialect, environment=environment)
