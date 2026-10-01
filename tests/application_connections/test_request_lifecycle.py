"""Application-owned request boundaries on a reusable DB and worker thread."""
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable
from tests.native_support import postgres_dsn


class Item(SqlTable):
    def trigger_onInserted(self, record):
        if self.db.currentEnv.get('fail_hook'):
            raise ValueError('hook failure')


class Request:
    """Example application object, not a new Asqueel API."""
    def __init__(self, shared_db, user):
        self.shared_db, self.user = shared_db, user
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = self.shared_db
            self._db.clearCurrentEnv()
            self._db.updateEnv(user=self.user, locale='it_IT')
        return self._db

    def cleanup(self):
        try:
            self.shared_db.closeConnection()
        finally:
            self.shared_db.clearCurrentEnv()


@pytest.mark.parametrize('backend', ['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)])
@pytest.mark.parametrize('failure', ['application', 'hook', 'sql', 'before', 'after'])
def test_next_request_inherits_no_pending_work_or_context(tmp_path, backend, failure):
    schema = 'request_' + uuid4().hex

    class Configuration(SqlDatabaseConfig):
        def main(self, root):
            if backend == 'sqlite':
                database = root.db()
                database.connection(name=str(tmp_path / 'requests.db'), implementation='sqlite')
            else:
                database = root.db(conninfo=postgres_dsn())
            table = database.schemas().schema(schema).tables().table('item', pkey='id', x_table_class=Item)
            table.columns().column('id', dtype='I')

    db = AsqueelDb(Configuration)
    trace = []

    def fail():
        raise ValueError('callback failure')

    try:
        if backend == 'postgresql':
            db.execute(f'CREATE SCHEMA "{schema}"')
        db.execute(f'CREATE TABLE "{schema}".item (id INTEGER PRIMARY KEY)')
        db.commit()
        db.closeConnection()
        first = Request(db, 'alice')
        caught = None
        try:
            first.db.currentEnv['request_only'] = 'first'
            assert first.db.currentEnv['request_only'] == 'first'  # No reset on repeated access.
            with db.tempEnv(connectionName='auxiliary'):
                db.deferAfterCommit(lambda: trace.append('old auxiliary'))
            db.deferAfterCommit(lambda: trace.append('old main'))
            if failure == 'hook':
                db.currentEnv['fail_hook'] = True
            if failure == 'after':
                # Order matters: stop before a callback belonging to this request.
                db.rollback()
                db.deferAfterCommit(fail)
                db.deferAfterCommit(lambda: trace.append('unreached'))
            db.table('item').insert({'id': 1})
            if failure == 'sql':
                db.table('item').insert({'id': 1})
            elif failure == 'application':
                raise ValueError('request failure')
            elif failure == 'before':
                db.deferToCommit(fail)
            db.commit()
        except Exception as error:
            caught = error  # Application receives the error and chooses to end this request.
        finally:
            first.cleanup()
        assert caught is not None
        assert trace == []
        second = Request(db, 'bob')
        try:
            assert second.db.currentEnv == {'user': 'bob', 'locale': 'it_IT'}
            assert second.db is db
            assert db.outcome == 'not_started'
            assert db.table('item').query(columns='$id', order_by='$id').fetch() == (
                [{'id': 1}] if failure == 'after' else [])
            db.rollback()
            db.table('item').insert({'id': 2})
            db.deferAfterCommit(lambda: trace.append('new main'))
            db.commit()
            with db.tempEnv(connectionName='auxiliary'):
                db.execute('SELECT 1')
                db.commit()
            assert trace == ['new main']
        finally:
            second.cleanup()
        assert db.currentEnv == {}
    finally:
        try:
            db.closeConnection()
            if backend == 'postgresql':
                db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                db.commit()
        finally:
            db.close()
