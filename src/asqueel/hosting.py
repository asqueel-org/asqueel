"""Databases owned by a host — a server or one of its applications — by name.

A host mixes in :class:`AsqueelDbMixin` on its server and on its applications.
Names follow one rule: ``<owner>:<db>`` is a database of the owner named
``<owner>`` (an application), a name without a colon is a database of the
server. Taking a database hands the main :class:`~asqueel.SessionDb` of the
current call (``AsqueelDb.session()``); the first take of a call opens it, with
a fresh ``currentEnv``. A session already open in the call, taken through
another owner, is used as it is. :meth:`AsqueelDbMixin.release_databases`
closes every session of the calls this owner opened: the main one and the
named ones of the same call.
"""
from __future__ import annotations

from threading import Lock
from weakref import WeakSet

from .application import AsqueelDb, SessionDb

#: Name of the database ``db`` returns.
DEFAULT_DB = 'default'


class AsqueelDbMixin:
    """Asqueel databases of a server or an application.

    The host provides two members:

    - ``asqueel_owner_name``: ``''`` for the server, the application code for
      an application;
    - ``asqueel_owner(name)``: the owner with that name, ``''`` for the server.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._asqueel_dbs: dict[str, AsqueelDb] = {}
        # Owner state, not call state: the call is found through each database's
        # current session. Taken = reached through this owner; opened = this owner opened it.
        self._asqueel_reached: dict[AsqueelDb, None] = {}
        self._asqueel_taken_sessions: WeakSet[SessionDb] = WeakSet()
        self._asqueel_opened_sessions: WeakSet[SessionDb] = WeakSet()
        self._asqueel_lock = Lock()
        super().__init__(*args, **kwargs)

    @property
    def asqueel_owner_name(self) -> str:
        raise NotImplementedError(f'{type(self).__name__} must define asqueel_owner_name')

    def asqueel_owner(self, name: str) -> AsqueelDbMixin:
        raise NotImplementedError(f'{type(self).__name__} must define asqueel_owner(name)')

    @property
    def asqueel_dbs(self) -> dict[str, AsqueelDb]:
        """This owner's databases by name, without the owner prefix."""
        return self._asqueel_dbs

    @staticmethod
    def _call_main(shared: AsqueelDb) -> SessionDb | None:
        """The open main session of the current call on ``shared``, if any."""
        current = shared._current_session.get()
        if current is None or current._closed:
            return None
        main = current._call_sessions.get('_main_connection')
        return None if main is None or main._closed else main

    @property
    def taken_databases(self) -> list[SessionDb]:
        """The sessions taken through this owner in the current call, in order."""
        with self._asqueel_lock:
            reached = list(self._asqueel_reached)
            taken = set(self._asqueel_taken_sessions)
        return [main for shared in reached if (main := self._call_main(shared)) is not None and main in taken]

    def set_asqueel_db(self, name: str, source, **kwargs) -> AsqueelDb:
        """Build an :class:`AsqueelDb` from ``source`` and register it under ``name``.

        ``source`` is anything ``AsqueelDb`` accepts: a recipe, a registered
        name, a file, or a ``db`` node mounted in the host configuration.
        """
        if ':' in name:
            raise ValueError(f"{name!r}: the name of an owner's database has no ':'")
        if name in self.asqueel_dbs:
            raise ValueError(f'database {name!r} is already registered for this owner')
        db = AsqueelDb(source, **kwargs)
        self.asqueel_dbs[name] = db
        return db

    @property
    def db(self) -> SessionDb:
        """The main session of this owner's ``default`` database, or of the server's when it has none."""
        owner = self if DEFAULT_DB in self.asqueel_dbs else self.asqueel_owner('')
        return self._take(owner, DEFAULT_DB)

    def get_db(self, name: str) -> SessionDb:
        """``chat:alfadb`` is a database of application ``chat``; ``betadb`` one of the server."""
        owner_name, _, db_name = name.rpartition(':')
        return self._take(self.asqueel_owner(owner_name), db_name)

    def release_databases(self) -> None:
        """Close the sessions of the current call opened through this owner, the named ones of the call included.

        The call is reached through each database's current session, also when the
        application already closed the main one. A session that refuses to close
        stays tracked: a later release tries it again.
        """
        with self._asqueel_lock:
            reached = list(self._asqueel_reached)
            taken = set(self._asqueel_taken_sessions)
            opened = set(self._asqueel_opened_sessions)
        mains = []
        for shared in reached:
            current = shared._current_session.get()
            main = current._call_sessions.get('_main_connection') if current is not None else None
            if main is not None and main in taken:
                mains.append(main)
        error = None
        for main in reversed(mains):
            closed = True
            if main in opened:
                # Named sessions first, the main one last.
                for session in reversed(list(main._call_sessions.values())):
                    if session._closed:
                        continue
                    try:
                        session.close()
                    except BaseException as failure:
                        closed = False
                        if error is None:
                            error = failure
            if closed:
                with self._asqueel_lock:
                    self._asqueel_taken_sessions.discard(main)
                    self._asqueel_opened_sessions.discard(main)
        if error is not None:
            raise error

    def _take(self, owner: AsqueelDbMixin, db_name: str) -> SessionDb:
        shared = owner.asqueel_dbs.get(db_name)
        if shared is None:
            prefix = f'{owner.asqueel_owner_name}:' if owner.asqueel_owner_name else ''
            raise KeyError(f'no database {prefix}{db_name}')
        opened = self._call_main(shared) is None
        db = shared.session()
        with self._asqueel_lock:
            self._asqueel_reached.setdefault(shared)
            self._asqueel_taken_sessions.add(db)
            if opened:
                self._asqueel_opened_sessions.add(db)
        return db
