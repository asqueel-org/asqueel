"""Public application API acceptance against PostgreSQL, with independent observers."""
from tests.unit_of_work import completed
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, SqlTable, TransactionStateError, build_database
from asqueel.application_table import RecordMultipleRowsError, RecordNotFoundError
from asqueel.contracts import EnvironmentMismatchError
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


class AuditedItem(SqlTable):
    def trigger_onInserting(self, record):
        record['name'] = record['name'].strip()

    def trigger_onInserted(self, record):
        self.db.table('app.audit').insert({'id': record['id'], 'item_id': record['id']})
        if record['name'] == 'fail':
            raise ValueError('post-insert hook rejected record')


@pytest.fixture
def application():
    dsn = postgres_dsn()
    schema = 'application_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        observer.execute(sql.SQL('CREATE TABLE {}.item (id integer PRIMARY KEY, name text NOT NULL)')
                         .format(sql.Identifier(schema)))
        observer.execute(sql.SQL('CREATE TABLE {}.audit (id integer PRIMARY KEY, item_id integer '
                                 'NOT NULL REFERENCES {}.item(id))')
                         .format(sql.Identifier(schema), sql.Identifier(schema)))

        class Recipe(SqlDatabaseConfig):
            def main(self, root):
                tables = root.db('acceptance', conninfo=dsn).schemas().schema(
                    'app', x_sql_schema=schema).tables()
                item = tables.table('item', pkey='id', x_table_class=AuditedItem).columns()
                item.column('id', dtype='I')
                item.column('name', dtype='T', notnull=True)
                audit = tables.table('audit', pkey='id').columns()
                audit.column('id', dtype='I')
                audit.column('item_id', dtype='I').relation('app.item.id', foreign_key=True)

        db = build_database(Recipe)

        def rows(table):
            return observer.execute(sql.SQL('SELECT * FROM {}.{} ORDER BY id').format(
                sql.Identifier(schema), sql.Identifier(table))).fetchall()

        try:
            yield db, rows
        finally:
            db.close()
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_manual_unit_of_work_is_shared_and_invisible_until_explicit_commit(application):
    db, rows = application
    item = db.table('item')
    assert item is db.table('app.item')
    assert db.table('audit').relation('item_id').target is item
    result = item.insert({'id': 1, 'name': ' first '})
    assert result.rows == [{'id': 1, 'name': 'first'}]
    item.insert({'id': 2, 'name': 'second'})
    assert item.query(order_by='$id').fetch() == [
        {'id': 1, 'name': 'first'}, {'id': 2, 'name': 'second'}]
    assert db.table('audit').query(order_by='$id').fetch() == [
        {'id': 1, 'item_id': 1}, {'id': 2, 'item_id': 2}]
    assert rows('item') == rows('audit') == []
    db.commit()
    assert rows('item') == [(1, 'first'), (2, 'second')]
    assert rows('audit') == [(1, 1), (2, 2)]
    assert db.outcome == 'committed'


def test_manual_rollback_and_close_discard_cross_table_writes(application):
    db, rows = application
    db.table('item').insert({'id': 1, 'name': 'rollback'})
    db.rollback()
    assert rows('item') == rows('audit') == []
    db.table('item').insert({'id': 2, 'name': 'close'})
    db.close()
    assert db.outcome == 'rolled_back'
    assert rows('item') == rows('audit') == []


def test_transaction_context_commits_hooks_together_and_rolls_back_hook_failure(application):
    db, rows = application
    with completed(db) as connection:
        assert connection is db
        db.table('item').insert({'id': 1, 'name': 'success'})
        assert rows('item') == rows('audit') == []
    assert rows('item') == [(1, 'success')]
    assert rows('audit') == [(1, 1)]
    with pytest.raises(ValueError, match='post-insert hook'):
        with completed(db):
            db.table('item').insert({'id': 2, 'name': 'fail'})
    assert rows('item') == [(1, 'success')]
    assert rows('audit') == [(1, 1)]


def test_caught_hook_error_remains_rollback_only_and_cannot_commit(application):
    db, rows = application
    with pytest.raises(ValueError, match='post-insert hook'):
        db.table('item').insert({'id': 1, 'name': 'fail'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()
    assert rows('item') == rows('audit') == []
    db.rollback()
    db.table('item').insert({'id': 2, 'name': 'recovered'})
    db.commit()
    assert rows('item') == [(2, 'recovered')]
    assert rows('audit') == [(2, 2)]


def test_query_compiles_in_terminal_environment_and_record_refreshes_explicitly(application):
    db, rows = application
    with completed(db):
        db.table('item').insert({'id': 1, 'name': 'same'})
        db.table('item').insert({'id': 2, 'name': 'same'})
    query = db.table('item').query(where='$id=:env_item')
    with db.temp_env(item=1):
        compiled = query.compiled
        assert query.fetch() == [{'id': 1, 'name': 'same'}]
    with db.temp_env(item=2):
        assert query.fetch() == [{'id': 2, 'name': 'same'}]
        with pytest.raises(EnvironmentMismatchError):
            db.execute(compiled)
    record = db.table('item').record(1)
    assert record.output('dict') == {'id': 1, 'name': 'same'}
    db.table('item').update({'name': 'changed'}, where='$id=:id', params={'id': 1})
    assert record.output('dict')['name'] == 'same'
    record.refresh()
    assert record.output('dict')['name'] == 'changed'
    db.rollback()
    assert rows('item') == [(1, 'same'), (2, 'same')]
    with pytest.raises(RecordNotFoundError):
        db.table('item').record(99).output('dict')
    with pytest.raises(RecordMultipleRowsError):
        db.table('item').record(where='$name=:name', name='same').output('dict')


def test_caught_hook_error_cannot_turn_context_exit_into_success(application):
    db, rows = application
    with pytest.raises(TransactionStateError, match='rollback-only'):
        with completed(db):
            db.table('item').insert({'id': 1, 'name': 'first'})
            with pytest.raises(ValueError, match='post-insert hook'):
                db.table('item').insert({'id': 2, 'name': 'fail'})
    assert rows('item') == rows('audit') == []
    assert db.outcome == 'rolled_back'


def test_database_constraint_failure_rolls_back_previous_operations(application):
    db, rows = application
    with pytest.raises(psycopg.errors.UniqueViolation):
        with completed(db):
            db.table('item').insert({'id': 1, 'name': 'first'})
            db.table('item').insert({'id': 1, 'name': 'duplicate'})
    assert rows('item') == rows('audit') == []
    assert db.outcome == 'rolled_back'


def test_named_connections_have_independent_visibility_and_physical_identity(application):
    from asqueel.contracts import CompiledQuery
    db, rows = application
    def pid():
        return db.execute(CompiledQuery('SELECT pg_backend_pid() AS pid')).rows[0]['pid']
    main_pid = pid()
    db.table('item').insert({'id': 10, 'name': 'main pending'})
    with db.tempEnv(connectionName='independent'):
        other_pid = pid()
        assert other_pid != main_pid
        assert db.table('item').query().fetch() == []
        db.table('item').insert({'id': 20, 'name': 'other committed'})
        db.commit()
        assert pid() == other_pid
        assert rows('item') == [(20, 'other committed')]
        db.rollback()
    assert pid() == main_pid
    db.rollback()
    assert rows('item') == [(20, 'other committed')]
    assert rows('audit') == [(20, 20)]
    assert pid() == main_pid


def test_sql_error_in_named_connection_rolls_back_hooks_and_allows_reuse(application):
    db, rows = application
    db.table('item').insert({'id': 10, 'name': 'main pending'})
    with db.tempEnv(connectionName='independent'):
        db.table('item').insert({'id': 20, 'name': 'must disappear'})
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.table('item').insert({'id': 20, 'name': 'duplicate'})
        assert db.outcome == 'rolled_back'
        assert db.table('item').query().fetch() == []
        db.table('item').insert({'id': 30, 'name': 'recovered'})
        db.commit()
    assert rows('item') == [(30, 'recovered')]
    db.commit()
    assert rows('item') == [(10, 'main pending'), (30, 'recovered')]
    assert rows('audit') == [(10, 10), (30, 30)]


def test_shared_database_threads_have_independent_postgres_connections(application):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db, rows = application
    barrier = Barrier(2)

    def worker(key, commit):
        try:
            db.updateEnv(worker=key)
            with db.tempEnv(connectionName='worker'):
                db.table('item').insert({'id': key, 'name': f'worker {key}'})
                barrier.wait(timeout=10)
                assert db.currentEnv['worker'] == key
                if commit:
                    with completed(db):
                        pass  # Includes the insert and its audit hook already pending.
                else:
                    db.rollback()
        finally:
            db.closeConnection()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, 301, True), pool.submit(worker, 302, False)]
        for future in futures:
            future.result()
    assert rows('item') == [(301, 'worker 301')]
    assert rows('audit') == [(301, 301)]
    assert db.currentEnv == {}
    with completed(db):
        db.table('item').insert({'id': 303, 'name': 'main'})
    assert rows('audit') == [(301, 301), (303, 303)]
