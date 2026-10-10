"""Databases owned by a host — a server or one of its applications — by name.

A host mixes in :class:`AsqueelDbMixin` on its server and on its applications.
Names follow one rule: ``<owner>:<db>`` is a database of the owner named
``<owner>`` (an application), a name without a colon is a database of the
server. Every database taken during a call is taken with
:meth:`~asqueel.runtime.Database.acquire`, which clears the context on the
first take; :meth:`AsqueelDbMixin.release_databases` closes, on the current
thread, the databases taken through that owner. One call runs on one thread.
"""
from __future__ import annotations

from threading import local

from .application import AsqueelDb

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
        self._asqueel_taken = local()
        super().__init__(*args, **kwargs)

    @property
    def asqueel_owner_name(self) -> str:
        raise NotImplementedError(f'{type(self).__name__} must define asqueel_owner_name')

    def asqueel_owner(self, name: str) -> AsqueelDbMixin:
        raise NotImplementedError(f'{type(self).__name__} must define asqueel_owner(name)')

    @property
    def asqueel_dbs(self) -> dict[str, AsqueelDb]:
        """This owner's databases by local name."""
        return self._asqueel_dbs

    @property
    def taken_databases(self) -> list[AsqueelDb]:
        """The databases taken through this owner on the current thread, in order."""
        if not hasattr(self._asqueel_taken, 'dbs'):
            self._asqueel_taken.dbs = []
        dbs: list[AsqueelDb] = self._asqueel_taken.dbs
        return dbs

    def set_asqueel_db(self, name: str, source, **kwargs) -> AsqueelDb:
        """Build an :class:`AsqueelDb` from ``source`` and register it under ``name``.

        ``source`` is anything ``AsqueelDb`` accepts: a recipe, a registered
        name, a file, or a ``db`` node mounted in the host configuration.
        """
        if ':' in name:
            raise ValueError(f"{name!r}: a local database name has no ':'")
        if name in self.asqueel_dbs:
            raise ValueError(f'database {name!r} is already registered for this owner')
        db = AsqueelDb(source, **kwargs)
        self.asqueel_dbs[name] = db
        return db

    @property
    def db(self) -> AsqueelDb:
        """This owner's ``default`` database, or the server's when it has none."""
        owner = self if DEFAULT_DB in self.asqueel_dbs else self.asqueel_owner('')
        return self._take(owner, DEFAULT_DB)

    def get_db(self, name: str) -> AsqueelDb:
        """``chat:alfadb`` is a database of application ``chat``; ``betadb`` one of the server."""
        owner_name, _, local_name = name.rpartition(':')
        return self._take(self.asqueel_owner(owner_name), local_name)

    def release_databases(self) -> None:
        """Close, on the current thread, every database taken through this owner."""
        taken = self.taken_databases
        error = None
        while taken:
            db = taken.pop()
            try:
                db.closeConnection()
            except BaseException as failure:
                if error is None:
                    error = failure
        if error is not None:
            raise error

    def _take(self, owner: AsqueelDbMixin, local_name: str) -> AsqueelDb:
        db = owner.asqueel_dbs.get(local_name)
        if db is None:
            prefix = f'{owner.asqueel_owner_name}:' if owner.asqueel_owner_name else ''
            raise KeyError(f'no database {prefix}{local_name}')
        db.acquire()
        taken = self.taken_databases
        if db not in taken:
            taken.append(db)
        return db
