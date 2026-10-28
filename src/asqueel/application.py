"""The configured database: model, environment, named connections and the write cycle."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import replace
import datetime
from importlib import import_module
import locale
import logging
import os
import re
from threading import Lock
from types import MappingProxyType
from typing import Any, cast
from uuid import uuid4
from weakref import WeakSet

from genro_bag import Bag

from . import cached_fetch
from .application_table import SqlTable
from .compiler import QueryCompiler
from .configuration import SqlConfigHandler, SqlDatabaseConfig, compose_recipe
from .contracts import CompiledQuery, UnsupportedFeatureError, not_available, refused_property
from .environment import _TRANSACTION_KEYS, _copy_values, environment_arguments
from .errors import DeferredCommitError, MigrationError, TransactionStateError
from .hierarchical import HierarchicalHandler
from .runtime import SqlCursor, _ConnectionState, connection_settings
from .triggers import TriggerStack
from .write_compiler import WriteCompiler
from .db_write import WriteMixin

# Statements that read: closing a session after them alone is not closing with pending work.
# A WITH that modifies data and a PRAGMA that assigns are writes.
_READ_STATEMENT = re.compile(r'\s*(SELECT|SHOW|EXPLAIN|VALUES)\b', re.IGNORECASE)
_READ_WITH = re.compile(r'\s*WITH\b', re.IGNORECASE)
_DATA_CHANGE = re.compile(r'\b(INSERT|UPDATE|DELETE|MERGE)\b', re.IGNORECASE)
_READ_PRAGMA = re.compile(r'\s*PRAGMA\b[^=]*$', re.IGNORECASE)


def _reads_only(sql: str) -> bool:
    if _READ_STATEMENT.match(sql) or _READ_PRAGMA.match(sql):
        return True
    return bool(_READ_WITH.match(sql)) and not _DATA_CHANGE.search(sql)


class AsqueelDb(WriteMixin):
    """Load a configured database by registered name, recipe, folder, file or mounted node.

    Construction validates the model without connecting. The database holds the
    model and the configuration shared by every call; it executes nothing.
    ``session()`` returns the :class:`SessionDb` of the current call, which holds
    the connection, ``currentEnv`` and the transaction state.

    A subclass may declare ``main(self, root)``: it writes the source as the
    ``main`` of a recipe, and the subclass is then called without a source.

    ``grammar`` is the configuration grammar a host document mounts to declare
    Asqueel databases in its own configuration: an element carrying
    ``_meta={"subbuilder": "db_class:grammar"}`` with ``db_class=AsqueelDb``.
    The database is written under that element starting from ``db()``, and
    ``AsqueelDb(node)`` builds it from the resulting ``db`` node.
    """

    grammar = SqlDatabaseConfig

    @property
    def tableMixin(self):
        raise not_available('tableMixin')

    @property
    def packageMixin(self):
        raise not_available('packageMixin')

    query = refused_property('db.query')
    whereTranslator = refused_property('db.whereTranslator')

    def migration_plan(self, *, allow_removals=False, foreignKeys=True, force=False, backup=False):
        """The DDL that would bring the live database to this model; changes nothing.

        Needs ``asqueel[migration]``. Returns the plan of
        :func:`asqueel_migration.plan_migration` (``sql``, ``warnings``, ``skipped``, ``empty``).
        ``foreignKeys``, ``force`` and ``backup`` are the legacy migration options
        (:func:`asqueel.migration.migration_plan`).
        """
        # asqueel-migration is an optional extra: import it only when migrating.
        from .migration import migration_plan
        return migration_plan(self, allow_removals=allow_removals, foreignKeys=foreignKeys,
                              force=force, backup=backup)

    def migrate(self, *, allow_removals=False, foreignKeys=True, force=False, backup=False):
        """Bring the live database to this model and return the result of the applied plan.

        Needs ``asqueel[migration]``. Raises :class:`~asqueel.migration.MigrationError`
        before any DDL when the backend cannot apply a change, and after applying
        when differences remain. The options are those of :meth:`migration_plan`.
        """
        from .migration import migrate
        return migrate(self, allow_removals=allow_removals, foreignKeys=foreignKeys,
                       force=force, backup=backup)

    def __init__(self, source=None, *, parents=None, environment: Mapping[str, Any] | None = None):
        if hasattr(self, 'main'):
            if source is not None:
                raise TypeError(f'{type(self).__name__} writes its own source in main(); do not pass one')
            source = SqlDatabaseConfig()
            self.main(source.source)
        elif source is None:
            raise TypeError('AsqueelDb requires a source, or a subclass with main(self, root)')
        recipe = compose_recipe(source, parents)
        self.config = config = SqlConfigHandler(recipe)
        implementation, conninfo, kwargs = connection_settings(config)
        self._ready = False
        self._connections: dict[str, _ConnectionState] = {}
        self._trigger_stack = TriggerStack()
        # Guards the session registry and the :memory: lend across threads.
        self._lock = Lock()
        self._current_session: ContextVar[SessionDb | None] = ContextVar(f'asqueel_session_{id(self)}', default=None)
        self._open_sessions: WeakSet[SessionDb] = WeakSet()
        # A subclass's methods (execute, write hooks, helpers) reach its sessions.
        self._session_class = SessionDb if type(self) is AsqueelDb else type(
            type(self).__name__, (SessionDb, type(self)), {})
        self._memory_connection = None
        self._in_memory = implementation == 'sqlite' and ((kwargs or {}).get('dbname') or conninfo) == ':memory:'
        # Legacy adapter loading: 'name' or 'name:module'; the module exposes SqlDbAdapter.
        if ':' in implementation:
            implementation, module = implementation.split(':')
        else:
            module = f'asqueel.adapters.{implementation}'
        self.implementation = implementation
        self.adapters: dict[str, Any] = {implementation: import_module(module).SqlDbAdapter(self)}
        self.conninfo = conninfo
        self.connect_kwargs = dict(kwargs or {})
        if self.connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        self._env_defaults = _copy_values(environment if environment is not None else {}, 'initialization')
        # The environment of the shared database's own compiler; a session starts from the defaults.
        self._env = _copy_values(self._env_defaults, 'initialization')
        self.name_long = config('name_long', default=None)
        self.name_short = config('name_short', default=None)
        self.comment = config('comment', default=None)
        self._compilers: dict[Any, QueryCompiler] = {}
        self._write_compilers: dict[Any, WriteCompiler] = {}
        self._tables: dict[str, SqlTable] = {}
        self._target = 'main'
        recipe.render(target=self)
        self._ready = True

    def reloadModel(self, source, *, parents=None):
        """Replace the model of an idle SQLite :memory: database, keeping its connection and rows.

        Does not migrate or reconnect: call migrate() afterwards, then take
        fresh tables and queries, because those of the previous model are
        invalidated. Requires exclusive use of this database (no concurrent
        threads), the same connection settings and the same SQL schemas.
        """
        shared = self.shared
        with shared._lock:
            sessions = list(shared._open_sessions)
        for session in sessions:
            session._check_idle()
        shared._reload_model(source, parents, sessions)

    def _reload_model(self, source, parents, sessions):
        old_settings = connection_settings(self.config)
        implementation, conninfo, kwargs = old_settings
        if implementation != 'sqlite' or ((kwargs or {}).get('dbname') or conninfo) != ':memory:':
            raise MigrationError('reloadModel is only supported for SQLite :memory: databases')
        recipe = compose_recipe(source, parents)
        config = SqlConfigHandler(recipe)
        if connection_settings(config) != old_settings:
            raise MigrationError('reloadModel cannot change connection settings')
        old_model = self.model
        try:
            recipe.render(target=self)
            if {t.sqlschema for t in self.model.tables.values()} != {t.sqlschema for t in old_model.tables.values()}:
                raise MigrationError('reloadModel cannot change SQL schemas')
        except BaseException:
            # A refused or failed build leaves the previous model in place.
            if self.model is not old_model:
                self.model.db = None
                self.model = old_model
            raise
        self.config = config
        for db in (self, *sessions):
            db._compilers.clear()
            db._write_compilers.clear()
            db._tables.clear()
            for key in [key for key in db._env if key.startswith('_virtual_columns_')]:
                del db._env[key]
        old_model.db = None

    def _check_idle(self):
        """Refuse to commit, roll back or bypass the unfinished work of a connection."""
        self._check_open()
        if len(self._connections) > 1:
            raise MigrationError('reloadModel requires a single main connection')
        if not self.usingMainConnection() or self.adapter.dialect != 'sqlite':
            raise MigrationError('In-memory migration requires the main SQLite connection')
        for state in self._connections.values():
            self._check_connection_usable(state)
            self._check_connection_completion(state)
            deferred = any(self.currentEnv.get(self._deferred_key(state, key)) for key in (
                'to_commit_defer_calls', 'after_commit_defer_calls', '_pendingExceptions'))
            connection = state['connection']
            if (state['pending'] or state['write_depth'] or deferred
                    or (connection is not None and connection.in_transaction)):
                raise TransactionStateError(
                    'In-memory schema changes require no pending work; commit or rollback first')


    @property
    def shared(self):
        """The AsqueelDb shared by every call: this database itself."""
        return self

    def _as_current(self):
        """The shared database is never the current session."""
        return nullcontext()

    @property
    def adapter(self):
        """The adapter of the database implementation."""
        return self.adapters[self.implementation]

    def session(self, name=None, *, target='main', **env):
        """The SessionDb of the current call: the main one, or the one called ``name``.

        A call reuses its sessions by name until they are closed; once its
        current session is closed, the next ``session()`` starts a new call.
        ``target`` is the configured connection the session connects to;
        ``env`` is applied to the ``currentEnv`` of a new session.
        """
        self._check_open()
        name = name or '_main_connection'
        current = self._current_session.get()
        calls = {} if current is None or current._closed else current._call_sessions
        found = calls.get(name)
        if found is not None and not found._closed:
            if env:
                raise TransactionStateError(f'session {name!r} of this call is already open')
            return found
        with self._lock:
            if self._in_memory and any(not session._closed for session in self._open_sessions):
                raise TransactionStateError('a :memory: database lends its connection to one session at a time')
            found = calls[name] = self._session_class(self, name, target, env, calls)
            self._open_sessions.add(found)
        # The main session anchors the call; a named one only when it opens the call.
        if current is None or current._closed or name == '_main_connection':
            self._current_session.set(found)
        return found

    def close(self) -> None:
        """Close every open session of this database, then the :memory: connection.

        When a session refuses to close, the :memory: connection stays open and the error is raised.
        """
        with self._lock:
            sessions = list(self._open_sessions)
        error = None
        for session in sessions:
            try:
                session.close()
            except BaseException as failure:
                if error is None:
                    error = failure
                else:
                    error.add_note(f'Another session cleanup failed: {type(failure).__name__}')
        if error is not None:
            raise error
        connection, self._memory_connection = self._memory_connection, None
        if connection is not None:
            self.adapter.close(connection)

    def _check_open(self) -> None:
        if not self._ready:
            raise TransactionStateError('Database object graph is not ready')

    @property
    def _write_depth(self):
        """Table writes in progress on the selected named connection."""
        return self._connection_state['write_depth']

    def _writing(self) -> bool:
        return any(state['write_depth'] for state in self._connections.values())

    @property
    def currentConnectionName(self) -> str:
        self._check_open()
        name = self._env_values.get('connectionName') or '_main_connection'
        if not isinstance(name, str):
            raise TypeError('connectionName must be a string')
        return name

    def usingMainConnection(self) -> bool:
        return self.currentConnectionName == '_main_connection'

    def _check_store(self) -> None:
        store = self._env_values.get('storename')
        if store and store != '_main_db':
            raise UnsupportedFeatureError(f'environment key storename={store!r}: database stores are not available in this release')

    @property
    def _connection_state(self) -> _ConnectionState:
        raise TransactionStateError('The shared AsqueelDb holds no connection; use db.session()')

    def _new_connection_state(self) -> _ConnectionState:
        self._check_open()
        self._check_store()
        name = self.currentConnectionName
        if name not in self._connections:
            self._connections[name] = dict(
                connection=None, pending=False, wrote=False, lock=Lock(),
                committing=False, completion_failed=False, connection_name=name,
                failed=False, executing=False, execution_error=None,
                execution_count=0, write_depth=0, cursors=WeakSet(), session=self,
            )
        return self._connections[name]

    @property
    def _env_values(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._env)

    @property
    def currentEnv(self) -> dict[str, Any]:
        """The live mapping of this database; a session owns its own."""
        self._check_open()
        return self._env_values

    @currentEnv.setter
    def currentEnv(self, values: dict[str, Any]) -> None:
        self._check_open()
        if not isinstance(values, dict):
            raise TypeError('currentEnv must be a dictionary')
        self._env = values

    def environment_snapshot(self) -> Mapping[str, Any]:
        """A detached read-only copy of currentEnv, with the workdate/locale defaults resolved."""
        # The deferred-call queues, pending exceptions and virtual-column containers
        # live in currentEnv as legacy; they are not SQL values and are not copied.
        values = _copy_values({key: value for key, value in self._env_values.items()
                               if not _TRANSACTION_KEYS.fullmatch(key)}, 'snapshot')
        values['workdate'] = self._env_values.get('workdate') or datetime.date.today()
        values['locale'] = self._default_locale()
        return MappingProxyType(values)

    def _default_locale(self):
        if self._env_values.get('locale'):
            return self._env_values['locale']
        # An explicitly empty GNR_LOCALE selects the static fallback, as in legacy.
        # Locale identifiers are context values, deliberately not validated.
        configured = os.environ.get('GNR_LOCALE') if 'GNR_LOCALE' in os.environ else locale.getlocale()[0]
        return configured or 'en_GB'

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
        return self.currentEnv.get('workdate') or datetime.date.today()

    @workdate.setter
    def workdate(self, value):
        self.currentEnv['workdate'] = value

    @property
    def locale(self):
        self._check_open()
        return self._default_locale()

    @locale.setter
    def locale(self, value):
        self.currentEnv['locale'] = value

    @contextmanager
    def tempEnv(self, **values: Any):
        """Overlay values on currentEnv and restore them on exit, as legacy."""
        current = self.currentEnv
        saved = {key: current[key] for key in values if key in current}
        added = {key: value for key, value in values.items() if key not in current}
        current.update(values)
        try:
            yield self
        finally:
            current = self.currentEnv
            for key, value in added.items():
                if current.get(key) == value:
                    current.pop(key, None)
            current.update(saved)

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
        query: CompiledQuery = self.adapter.prepare_sql(sql, sqlargs, self.environment_snapshot())
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

    def cleanupCachedTable(self, owner=None):
        """Drop the cached fetches of ``owner`` (``'foo'``, ``'foo,bar'``), or of every owner but those (``'!(foo,bar)'``)."""
        cached_fetch.cleanup(self, owner)

    def vacuum(self, table: str = '', full: bool = False) -> None:
        """Reclaim storage of the database or of ``table`` (its SQL name), on a separate connection.

        The work pending on this session would hold the locks the separate connection waits for.
        """
        self._check_open()
        if self._connection_state['pending']:
            raise TransactionStateError('vacuum requires no pending work on this session; commit or rollback first')
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
        """Roll back and close the connection of this session, as legacy.

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

    def _close_connections(self, claimed: bool = False) -> None:
        error = None
        for state in self._connections.values():
            try:
                self._close_connection(state, claimed)
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
        blocks = state['session']._env_values.setdefault(self._deferred_key(state, queue), Bag())
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
        state['session']._env_values.setdefault(self._deferred_key(state, '_pendingExceptions'), []).append(exception)

    def _invoke_deferred(self, state: _ConnectionState, queue: str) -> None:
        context: dict[str, Any] = {'onCommittingStep': True}
        if state['connection_name'] is not None:
            context['connectionName'] = state['connection_name']
        with self.tempEnv(**context):
            self._drain_deferred(state, queue)

    def _drain_deferred(self, state: _ConnectionState, queue: str) -> None:
        blocks = state['session']._env_values.get(self._deferred_key(state, queue))
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

    def _pop_transaction_key(self, state: _ConnectionState, queue: str) -> Any:
        """Pop a deferred queue or the pending exceptions of ``state`` from the currentEnv of its session."""
        return state['session']._env_values.pop(self._deferred_key(state, queue), None)

    def _clear_deferred(self, state: _ConnectionState) -> None:
        self._pop_transaction_key(state, 'to_commit_defer_calls')
        self._pop_transaction_key(state, 'after_commit_defer_calls')
        self._pop_transaction_key(state, '_pendingExceptions')

    def _claim(self, states) -> None:
        """Check every state and mark it executing, atomically per state; on a refusal none stays claimed."""
        claimed = []
        try:
            for state in states:
                with state['lock']:
                    self._check_connection_completion(state)
                    state['executing'] = True
                claimed.append(state)
        except BaseException:
            for state in claimed:
                state['executing'] = False
            raise

    def _check_connection_available(self, state: _ConnectionState) -> None:
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
        for key in self._env_values:
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
                query.environment_keys, self.environment_snapshot())})
        # Check and claim at once: a second thread of the call is refused, never interleaved.
        with state['lock']:
            self._check_connection_usable(state)
            state['executing'] = True
        state['execution_count'] += 1
        state['execution_error'] = None
        try:
            if state['connection'] is None:
                state['connection'] = state['session']._open_connection(adapter)
            state['pending'] = True
            if not _reads_only(query.sql):
                state['wrote'] = True
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
            # The failed statement still holds the connection.
            self._finish(state, False, claim=False)
        except BaseException as cleanup_error:
            # The original execution error must remain catchable by callers.
            error.add_note(f'Automatic rollback failed: {type(cleanup_error).__name__}')
            raise error from cleanup_error

    def _mark_connection_failed(self, state: _ConnectionState) -> None:
        """Mark a failed domain operation even when no SQL has run yet."""
        state['failed'] = True

    def _discard_connection(self, state: _ConnectionState) -> None:
        # A cursor still referenced keeps its statement alive; on SQLite it keeps the file locked.
        # The record is weak: a cursor nobody references is released by the driver.
        for cursor in tuple(state['cursors']):
            cursor.close()
        connection, state['connection'] = state['connection'], None
        # The :memory: connection belongs to the shared AsqueelDb, which lends it.
        if connection is not None and connection is not self.shared._memory_connection:
            self.adapter.close(connection)

    def _finish(self, state: _ConnectionState, commit: bool, claim: bool = True) -> None:
        if not state['pending']:
            state['failed'] = False
            if not commit:
                self._clear_deferred(state)
            return
        if claim:
            with state['lock']:
                self._check_connection_available(state)
                state['executing'] = True
        else:
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
            state['wrote'] = False
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
                    pending_exceptions = self._pop_transaction_key(state, '_pendingExceptions')
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

    def _close_connection(self, state: _ConnectionState, claimed: bool = False) -> None:
        if not claimed:
            self._claim([state])
        error: BaseException | None = None
        try:
            try:
                self._finish(state, False, claim=False)
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


    @property
    def compiler(self):
        adapter = self.adapter
        if adapter not in self._compilers:
            self._compilers[adapter] = QueryCompiler(self.model, adapter, _db=self)
        return self._compilers[adapter]

    @property
    def write_compiler(self):
        """Compiler of insert, update and delete statements, separate from queries."""
        adapter = self.adapter
        if adapter not in self._write_compilers:
            self._write_compilers[adapter] = WriteCompiler(adapter)
        return self._write_compilers[adapter]

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType({name: table.dbtable for name, table in self.model.tables.items()})

    def table(self, name: str) -> SqlTable:
        """Return the registered operational table, preserving object identity."""
        self._check_open()
        found = self.model.table(name)
        if found is None:
            raise ValueError(f'Unknown package {name.split(".")[0]!r}')
        table: SqlTable = found.dbtable
        return table

    def package(self, name: str):
        self._check_open()
        return self.model.packages[name]

    def schema(self, name: str):
        self._check_open()
        raise UnsupportedFeatureError('SQL schemas are derived from packages')

    def _open_connection(self, adapter):
        conninfo, connect_kwargs = self._connection_settings()
        if connect_kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        shared = self.shared
        if not shared._in_memory:
            return adapter.connect(conninfo, **connect_kwargs)
        if shared._memory_connection is None:
            shared._memory_connection = adapter.connect(conninfo, **connect_kwargs)
        else:
            # A session dropped without close() may have left its transaction open.
            adapter.rollback(shared._memory_connection)
        return shared._memory_connection

    def _connection_settings(self, target=None):
        implementation, conninfo, kwargs = connection_settings(self.config, target or self._target)
        if implementation != self.model.implementation:
            raise ValueError('Configured implementation changed after database construction')
        kwargs = dict(kwargs or {})
        if self.implementation == 'sqlite':
            kwargs['schemas'] = sorted({table.sqlschema for table in self.model.tables.values()})
        return conninfo, kwargs


class SessionDb(AsqueelDb):
    """One call on a shared :class:`AsqueelDb`: its connection, ``currentEnv`` and transaction.

    Built by :meth:`AsqueelDb.session`. The model and the configuration are
    those of the shared database. As a context manager it is the current
    session of the body and closes at exit: a clean exit with uncommitted
    work rolls back and logs a warning, an exit by exception rolls back.
    """

    def __init__(self, shared, name, target, env, call_sessions):
        self._shared = shared
        self.implementation = shared.implementation
        self.conninfo = shared.conninfo
        self.connect_kwargs = shared.connect_kwargs
        self.name_long, self.name_short, self.comment = shared.name_long, shared.name_short, shared.comment
        self._ready = True
        self._closed = False
        self._connection_name = name
        self._target = target
        self._call_sessions = call_sessions
        # Sessions of the call opened by tempEnv(connectionName=...) on this one; they close with it.
        self._routed_sessions: list[SessionDb] = []
        self._tokens: list[Any] = []
        self._connections = {}
        self._trigger_stack = TriggerStack()
        self._env_defaults = shared._env_defaults
        self._env = _copy_values(shared._env_defaults, 'session initialization')
        self._env.update(env)
        self.adapters = {}
        self._compilers = {}
        self._write_compilers = {}
        self._tables = {}

    @property
    def shared(self):
        return self._shared

    @property
    def model(self):
        return self.shared.model

    @property
    def config(self):
        return self.shared.config

    def session(self, name=None, *, target='main', **env):
        return self.shared.session(name, target=target, **env)

    def _check_open(self) -> None:
        if self._closed:
            raise TransactionStateError(f'Session {self._connection_name!r} is closed')

    @contextmanager
    def _as_current(self):
        """This session is the current one of the call for the block."""
        token = self.shared._current_session.set(self)
        try:
            yield self
        finally:
            self.shared._current_session.reset(token)

    def migration_plan(self, **options):
        self._lend_memory_connection()
        return super().migration_plan(**options)

    def migrate(self, **options):
        self._lend_memory_connection()
        return super().migrate(**options)

    def _lend_memory_connection(self):
        """Give the migration of a :memory: database the connection the shared database lends."""
        if self.shared._in_memory:
            state = self._connection_state
            if state['connection'] is None:
                state['connection'] = state['session']._open_connection(self.adapter)

    @property
    def adapter(self):
        """The adapter of the current implementation; ``currentImplementation`` overrides it."""
        implementation = self._env_values.get('currentImplementation') or self.implementation
        if implementation not in self.adapters:
            if implementation == self.implementation:
                adapter_class = type(self.shared.adapter)
            else:
                adapter_class = import_module(f'asqueel.adapters.{implementation}').SqlDbAdapter
            self.adapters[implementation] = adapter_class(self)
        return self.adapters[implementation]

    @property
    def currentConnectionName(self) -> str:
        self._check_open()
        return self._routed._connection_name

    @property
    def _routed(self):
        """The session of this call whose connection runs this one's statements.

        ``tempEnv(connectionName=...)`` names another session of the same call,
        opened on first use on the configured connection of that name (main
        when none is declared), as legacy; the environment stays this session's.
        """
        name = self._routed_name
        if name == self._connection_name:
            return self
        found = self._call_sessions.get(name)
        if found is None or found._closed:
            with self._as_current():
                found = self.shared.session(name, target=name)
            self._routed_sessions.append(found)
        return found

    @property
    def _routed_name(self) -> str:
        name = self._env_values.get('connectionName') or self._connection_name
        if not isinstance(name, str):
            raise TypeError('connectionName must be a string')
        return name

    def _routed_open(self):
        """The routed session if it is already open, without opening it."""
        name = self._routed_name
        if name == self._connection_name:
            return self
        found = self._call_sessions.get(name)
        return None if found is None or found._closed else found

    def _connection_settings(self, target=None):
        if target is None and self._routed_name != self._connection_name:
            routed = self._routed_open()
            # A routed session not opened yet would open on the connection of its name.
            target = routed._target if routed is not None else self._routed_name
        return super()._connection_settings(target)

    def vacuum(self, table: str = '', full: bool = False) -> None:
        """Reclaim storage on a separate connection; refused while this session or its routed one has pending work."""
        self._check_open()
        routed = self._routed_open()
        sessions = (self,) if routed in (None, self) else (self, routed)
        if any(state['pending'] for session in sessions for state in session._connections.values()):
            raise TransactionStateError('vacuum requires no pending work on this session; commit or rollback first')
        self.adapter.vacuum(table=table, full=full)

    @property
    def _connection_state(self) -> _ConnectionState:
        return self._routed._new_connection_state()

    @contextmanager
    def _write_operation(self):
        with self._as_current(), super()._write_operation():
            yield

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType({name: self.table(name) for name in self.model.tables})

    def table(self, name: str) -> SqlTable:
        """The table of this session, built on first request and then reused."""
        self._check_open()
        found = self.model.table(name)
        if found is None:
            raise ValueError(f'Unknown package {name.split(".")[0]!r}')
        table = self._tables.get(found.fullname)
        if table is None:
            table = self._tables[found.fullname] = type(found.dbtable)(found, self)
            # The handler executes: the one of the shared table cannot serve a session.
            if 'hierarchicalHandler' in vars(found.dbtable):
                table.hierarchicalHandler = HierarchicalHandler(table)
        return table

    def __enter__(self):
        self._check_open()
        self._tokens.append(self.shared._current_session.set(self))
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.shared._current_session.reset(self._tokens.pop())
        if exc is None:
            self._close(warn=True)
            return
        try:
            self._close(warn=False)
        except BaseException as cleanup:
            exc.add_note(f'Connection cleanup failed: {type(cleanup).__name__}')

    def close(self) -> None:
        """Roll back what is not committed, close the connection; the session refuses any later use."""
        self._close(warn=True)

    def _close(self, warn):
        if self._closed:
            return
        sessions = [self, *(routed for routed in self._routed_sessions if not routed._closed)]
        # Claim every connection of this session and of the ones it routed to before
        # changing anything: a close refused (a statement or a commit in progress) changes nothing.
        self._claim([state for session in sessions for state in session._connections.values()])
        error = None
        for session in reversed(sessions):
            try:
                session._release(warn)
            except BaseException as failure:
                error = error or failure
        if error is not None:
            raise error

    def _release(self, warn):
        """Roll back and close the connections this close has already claimed."""
        queues = ('to_commit_defer_calls', 'after_commit_defer_calls', '_pendingExceptions')
        pending = any(state['wrote'] or any(self._env.get(self._deferred_key(state, queue)) for queue in queues)
                      for state in self._connections.values())
        try:
            self._close_connections(claimed=True)
        finally:
            self._connections.clear()
            self._closed = True
            with self.shared._lock:
                self.shared._open_sessions.discard(self)
        if pending and warn:
            logging.getLogger(__name__).warning(
                'database %s, session %s: closed with uncommitted work, rolled back',
                self.model.name, self._connection_name)
