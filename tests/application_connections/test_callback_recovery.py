"""Public deferred-recovery behavior on both real data backends."""
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, TransactionStateError
from tests.native_support import postgres_dsn


@pytest.mark.parametrize('backend', ['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)])
@pytest.mark.parametrize('stage', ['before', 'after'])
@pytest.mark.parametrize('callback_writes', [False, True])
def test_failed_callback_retry_and_fresh_work(tmp_path, backend, stage, callback_writes):
    schema = 'callback_' + uuid4().hex

    class Configuration(SqlDatabaseConfig):
        def main(self, root):
            if backend == 'sqlite':
                database = root.db()
                database.connection(name=str(tmp_path / 'callbacks.db'), implementation='sqlite')
            else:
                database = root.db(conninfo=postgres_dsn())
            database.schemas().schema(schema).tables().table('event', pkey='id').columns().column('id', dtype='I')

    db = AsqueelDb(Configuration)
    observer = AsqueelDb(Configuration)
    trace = []
    error = ValueError('callback failed')

    def write(value):
        db.execute(f'INSERT INTO "{schema}".event VALUES (:value)', {'value': value})

    def visible():
        result = observer.execute(f'SELECT id FROM "{schema}".event ORDER BY id').rows
        observer.rollback()
        return [row['id'] for row in result]

    def fail():
        trace.append('failed')
        assert db.currentEnv['onCommittingStep'] is True
        if callback_writes:
            write(2)
        raise error

    try:
        if backend == 'postgresql':
            db.execute(f'CREATE SCHEMA "{schema}"')
        db.execute(f'CREATE TABLE "{schema}".event (id INTEGER PRIMARY KEY)')
        db.commit()
        write(1)
        register = db.deferToCommit if stage == 'before' else db.deferAfterCommit
        register(fail)
        register(lambda: trace.append('remaining'))
        if stage == 'before':
            db.deferAfterCommit(lambda: trace.append('after'))
        with pytest.raises(ValueError) as raised:
            db.commit()
        assert raised.value is error
        assert 'onCommittingStep' not in db.currentEnv
        assert trace == ['failed']
        if stage == 'before' or callback_writes:
            with pytest.raises(TransactionStateError):
                db.commit()
        else:
            db.commit()  # No pending transaction; no automatic queue retry.
            assert visible() == [1]
        assert trace == ['failed']
        continued = stage == 'after' and not callback_writes
        if continued:
            write(4)
            db.commit()
            assert trace == ['failed', 'remaining']
        db.rollback()
        durable = [1, 4] if continued else ([1] if stage == 'after' else [])
        assert visible() == durable
        write(3)
        db.deferAfterCommit(lambda: trace.append('fresh'))
        db.commit()
        assert visible() == sorted(durable + [3])
        assert trace == (['failed', 'remaining', 'fresh'] if continued else ['failed', 'fresh'])
    finally:
        observer.close()
        try:
            db.rollback()
            if backend == 'postgresql':
                db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                db.commit()
        finally:
            db.close()
