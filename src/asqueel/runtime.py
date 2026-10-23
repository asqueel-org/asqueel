"""Shared execution path, thread-local named connections and explicit completion."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Thread, local
from typing import Any, Iterator, TypedDict
from weakref import WeakSet

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
