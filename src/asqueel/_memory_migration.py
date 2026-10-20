"""Borrow the application's SQLite connection without taking ownership of it.

The optional migration package normally opens separate file connections for
introspection and DDL. A private :memory: database must use the application's
connection for both, including the post-apply comparison.
"""
from asqueel_migration.adapters.sqlite_adapter import SqliteAdapter, SqliteDatabase
from asqueel_migration.readers.sqlite_reader import SqliteReader

from .errors import MigrationError, TransactionStateError


def check_idle(db):
    """Do not commit, roll back or bypass an application's unfinished work."""
    db._check_open()
    if not db.usingMainConnection() or db.adapter.dialect != 'sqlite':
        raise MigrationError('In-memory migration requires the main SQLite connection')
    for state in db._connections.values():
        db._check_connection_usable(state)
        db._check_connection_completion(state)
        deferred = any(db.currentEnv.get(db._deferred_key(state, key)) for key in (
            'to_commit_defer_calls', 'after_commit_defer_calls', '_pendingExceptions'))
        connection = state['connection']
        if (state['pending'] or state['write_depth'] or deferred
                or (connection is not None and connection.in_transaction)):
            raise TransactionStateError(
                'In-memory schema changes require no pending work; commit or rollback first')


class _BorrowedReader(SqliteReader):
    def __init__(self, connection, schemas):
        super().__init__({'dbname': ':memory:'}, schemas=schemas)
        self._borrowed = connection

    def connect(self):
        self._conn = self._borrowed

    def close(self):
        # BaseReader closes after every comparison. It must not close the DB.
        self._conn = None


class _BorrowedAdapter(SqliteAdapter):
    def __init__(self, database):
        super().__init__(database)
        self._reader = _BorrowedReader(database._connection, database.schema_files())

    def execute(self, sql, autoCommit=False, manager=False):
        connection = self.database._connection
        if connection.in_transaction:
            raise TransactionStateError('Commit or rollback before applying a migration')
        try:
            connection.execute('BEGIN')
            for statement in self._split_statements(sql):
                connection.execute(statement)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


class MemoryDatabase(SqliteDatabase):
    """Migration facade over a borrowed, idle, application-owned connection."""

    def __init__(self, db, schemas):
        check_idle(db)
        state = db._connection_state
        conninfo, kwargs = db._connection_settings()
        if (kwargs.get('dbname') or conninfo) != ':memory:':
            raise MigrationError('In-memory migration requires a :memory: connection')
        if state['connection'] is None:
            state['connection'] = db.adapter.connect(conninfo, **kwargs)
        super().__init__({'dbname': ':memory:'}, application_schemas=schemas)
        self._connection = state['connection']
        self._adapter = _BorrowedAdapter(self)

    def schema_files(self):
        return {schema: ':memory:' for schema in self._application_schemas if schema != 'main'}

    def closeConnection(self):
        # The AsqueelDb owner alone ends the lifetime of the in-memory database.
        pass
