"""Shared execution path, thread-local named connections and explicit completion."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Thread, local
from typing import Any, Iterator, TypedDict
from weakref import WeakSet

from genro_bag import Bag
from genro_builders.contrib.config import ConfigHandler
from genro_toolbox import NamedList

from .errors import TransactionStateError
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


class SqlCursor:
    """The open cursor returned by ``db.execute``: rows read by name, as the legacy dict cursor.

    A driver error raised by a fetch rolls the connection back, as one raised by execute.
    """

    def __init__(self, db, state: _ConnectionState, cursor, columns=()):
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
def session(db, **env: Any):
    """The unit of work outside a request, as a legacy page request.

    Entry clears ``currentEnv`` and applies ``env``; exit, also when the body
    raises, calls ``closeConnection()``, which rolls back what was not
    committed. One session at a time per database and thread.
    """
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


def connection_settings(config, connection_name='main'):
    """Read standard config attributes, resolving EnvResolver via ConfigHandler."""
    prefix = 'connection'
    if connection_name not in ('main', '_main_connection') and isinstance(config, ConfigHandler):
        candidate = f'connection_{connection_name}'
        node = config.builder.source.get_node(f'{config.root_label}.{candidate}')
        if node is not None:
            prefix = candidate
        else:
            root = config.builder.source.get_node(config.root_label)
            if root is not None and isinstance(root.value, Bag) and any(
                    child.node_tag == 'connection' and {'database', 'dsn'}.intersection(child.attr)
                    for child in root.value):
                raise ValueError(f'Unknown named connection: {connection_name!r}')
    return _connection_settings(config, prefix)


def _connection_settings(config, prefix):
    def read(path, default=None):
        # ConfigHandler's generic None-as-missing semantics must not replace a
        # failed explicit resolver with the signature's default connection name.
        if isinstance(config, ConfigHandler):
            head, _, attribute = path.rpartition('.')
            node_path = '.'.join(filter(None, (config.root_label, prefix, head)))
            node = config.builder.source.get_node(node_path)
            if node is not None and attribute in node.attr:
                return node.get_value(_query_string=attribute)
        return config(f'{prefix}.{path}', default=default)

    name = read('name')
    has_connection = (isinstance(config, ConfigHandler)
                      and config.builder.source.get_node(f'{config.root_label}.{prefix}') is not None)
    if not has_connection and name is None:
        if isinstance(config, ConfigHandler):
            root = config.builder.source.get_node(config.root_label)
            if root is not None and isinstance(root.value, Bag) and any(
                    child.node_tag == 'connection' for child in root.value):
                raise ValueError('Named connections require an explicit main connection')
        return (config('implementation', default='sqlite'),
                config('conninfo', default=''), config('connect_kwargs', default=None))
    implementation = read('implementation')
    if implementation is None:
        implementation = config('implementation', default='sqlite')
    if config('conninfo', default='') or config('connect_kwargs', default=None):
        raise ValueError('Use connection or legacy conninfo/connect_kwargs, not both')
    fields = ('connect_timeout', 'application_name', 'sslmode', 'sslrootcert',
              'options', 'timeout', 'cached_statements', 'foreignKeys')
    options = {field: value for field in fields
               if (value := read(f'options.driver.{field}')) is not None}
    database = read('database')
    dsn = read('dsn')
    connection_node = (config.builder.source.get_node(f'{config.root_label}.{prefix}')
                       if isinstance(config, ConfigHandler) else None)
    explicit_database = connection_node is not None and 'database' in connection_node.attr
    explicit_dsn = connection_node is not None and 'dsn' in connection_node.attr
    if explicit_database and database is None:
        raise ValueError('connection.database must resolve to a nonempty database name')
    if explicit_dsn and dsn is None:
        raise ValueError('connection.dsn must resolve to a nonempty string')
    if (database is not None or dsn is not None) and implementation != config('implementation', default='sqlite'):
        raise ValueError('Named connections must use the database dialect')
    if dsn is not None:
        if database is not None or any(read(field) is not None
                                       for field in ('host', 'port', 'user', 'password')):
            raise ValueError('dsn and individual connection fields cannot be combined')
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError('connection.dsn must resolve to a nonempty string')
        if implementation.partition(':')[0] not in ('postgres', 'postgres3'):
            raise ValueError('dsn requires a PostgreSQL connection')
        return implementation, dsn, options
    name = database if database is not None else name
    if not isinstance(name, str) or not name.strip():
        raise ValueError('connection.name must resolve to a nonempty database name')
    options['dbname'] = name
    if implementation.partition(':')[0] == 'sqlite':
        if any(read(key) is not None
               for key in ('host', 'port', 'user', 'password')):
            raise ValueError('SQLite uses a filename, not host/user/password/port')
        if set(options) - {'dbname', 'timeout', 'cached_statements', 'foreignKeys'}:
            raise ValueError('Unsupported SQLite connection options')
        return implementation, '', options
    for name in ('host', 'port', 'user', 'password'):
        value = read(name)
        if value is not None:
            expected = int if name == 'port' else str
            if not isinstance(value, expected) or isinstance(value, bool):
                raise ValueError(f'connection.{name} resolved to an invalid type')
            options[name] = value
    if options.get('autocommit'):
        raise ValueError('Asqueel requires transactional connections, not autocommit')
    return implementation, '', options
