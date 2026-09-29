"""Public application API acceptance against PostgreSQL, with independent observers."""
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from genro_sql import SqlDatabaseConfig, SqlTable, TransactionStateError, build_database
from genro_sql.application_table import RecordMultipleRowsError, RecordNotFoundError
from genro_sql.contracts import EnvironmentMismatchError
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
    with db.transaction() as transaction:
        assert transaction is db
        db.table('item').insert({'id': 1, 'name': 'success'})
        assert rows('item') == rows('audit') == []
    assert rows('item') == [(1, 'success')]
    assert rows('audit') == [(1, 1)]
    with pytest.raises(ValueError, match='post-insert hook'):
        with db.transaction():
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
    with db.transaction():
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
    with pytest.raises(TransactionStateError, match='rolled back after a failed operation'):
        with db.transaction():
            db.table('item').insert({'id': 1, 'name': 'first'})
            with pytest.raises(ValueError, match='post-insert hook'):
                db.table('item').insert({'id': 2, 'name': 'fail'})
    assert rows('item') == rows('audit') == []
    assert db.outcome == 'rolled_back'


def test_database_constraint_failure_rolls_back_previous_operations(application):
    db, rows = application
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            db.table('item').insert({'id': 1, 'name': 'first'})
            db.table('item').insert({'id': 1, 'name': 'duplicate'})
    assert rows('item') == rows('audit') == []
    assert db.outcome == 'rolled_back'
