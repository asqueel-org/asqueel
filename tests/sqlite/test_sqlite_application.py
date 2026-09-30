"""SQLite exercises the same application lifecycle, not a parallel API."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable, TransactionStateError
from asqueel.cli import prepare_migration, run_migration


class Item(SqlTable):
    def trigger_onInserting(self, record):
        record['name'] = record['name'].strip()
    def trigger_onInserted(self, record):
        if record['name'] == 'fail':
            raise ValueError('hook failure')
    def trigger_onUpdating(self, record, old_record=None):
        record['name'] += '!'


def recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite', options={'timeout': 0.1})
            tables = db.schemas().schema('app').tables()
            columns = tables.table('item', pkey='id', x_table_class=Item).columns()
            columns.column('id', dtype='I')
            columns.column('name', dtype='T')
    return Recipe


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'sample.db'
    db = AsqueelDb(recipe(path))
    db.execute('CREATE TABLE app.item (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    db.commit()
    try:
        yield db, path
    finally:
        db.close()


def observed(path):
    with sqlite3.connect(path.with_name('sample_app.db')) as connection:
        return connection.execute('SELECT id, name FROM item ORDER BY id').fetchall()


def test_normal_and_raw_commands_share_execute_and_explicit_commit(database):
    db, path = database
    table = db.table('item')
    assert table.insert({'id': 1, 'name': '  Ada  '}).rows == [{'id': 1, 'name': 'Ada'}]
    assert observed(path) == []
    db.commit()
    assert observed(path) == [(1, 'Ada')]
    table.update({'id': 1, 'name': 'Grace'})
    assert table.query().fetch()[0]['name'] == 'Grace!'
    table.raw_update({'id': 1, 'name': 'raw'})
    table.raw_insert({'id': 2, 'name': ' fail '})
    db.commit()
    assert observed(path) == [(1, 'raw'), (2, ' fail ')]
    table.raw_delete(1)
    table.delete(2)
    db.rollback()
    assert len(observed(path)) == 2


def test_hook_failure_blocks_commit_and_rollback_restores_usability(database):
    db, path = database
    with pytest.raises(ValueError, match='hook failure'):
        db.table('item').insert({'id': 1, 'name': 'fail'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()
    db.rollback()
    assert observed(path) == []
    db.table('item').insert({'id': 2, 'name': 'ok'})
    db.commit()
    assert observed(path) == [(2, 'ok')]


def test_parameters_environment_percent_literals_and_sql_error(database):
    db, path = database
    with db.tempEnv(user="O'Reilly"):
        result = db.execute("SELECT :env_user AS name, '50% :literal' AS label")
        assert result.rows == [{'name': "O'Reilly", 'label': '50% :literal'}]
    db.rollback()
    db.execute('INSERT INTO app.item VALUES (:id, :name)', {'id': 1, 'name': 'ok'})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('INSERT INTO app.item VALUES (:id, :name)', {'id': 1, 'name': 'duplicate'})
    assert observed(path) == []
    assert db.outcome == 'rolled_back'
    db.table('item').raw_insert({'id': 2, 'name': 'retry'})
    db.commit()


def test_threads_and_named_connections_use_same_files_with_independent_state(database):
    db, path = database
    def worker():
        try:
            assert db.currentEnv == {}
            with db.tempEnv(connectionName='worker', user='worker'):
                db.table('item').raw_insert({'id': 1, 'name': 'worker'})
                db.commit()
        finally:
            db.closeConnection()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()
    assert observed(path) == [(1, 'worker')]
    assert db.currentEnv == {}
    with db.tempEnv(connectionName='other'):
        db.table('item').raw_update({'id': 1, 'name': 'other'})
        db.rollback()
    assert observed(path) == [(1, 'worker')]


def test_sqlite_cli_reuses_existing_migrator_and_file_layout(tmp_path):
    path = tmp_path / 'sample.db'
    db = AsqueelDb(recipe(path))
    try:
        assert run_migration(db, 'apply') == 0
        db.table('item').insert({'id': 1, 'name': 'migrated'})
        db.commit()
        assert observed(path) == [(1, 'migrated')]
        migrator, changes = prepare_migration(db)
        try:
            assert not changes.strip()
        finally:
            migrator.db.closeConnection()
    finally:
        db.close()


def test_two_schema_example_migration_and_relationship_query(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setenv('ASQUEEL_SQLITE_FILE', str(tmp_path / 'example.db'))
    db = AsqueelDb(Path(__file__).parents[2] / 'examples/sqlite/configure.py')
    try:
        assert run_migration(db, 'apply') == 0
        db.table('contacts.customer').insert({'id': 1, 'name': 'Ada'})
        db.table('sales.invoice').insert({'id': 10, 'customer_id': 1, 'description': 'Example'})
        db.commit()
        rows = db.table('sales.invoice').query(
            columns='$id, @customer_id.name AS customer, $description', offset=0,
        ).fetch()
        assert rows == [{'id': 10, 'customer': 'Ada', 'description': 'Example'}]
        db.commit()
        assert (tmp_path / 'example_contacts.db').exists()
        assert (tmp_path / 'example_sales.db').exists()
    finally:
        db.close()


def test_another_named_connection_times_out_without_losing_first_transaction(database):
    db, path = database
    db.table('item').raw_insert({'id': 1, 'name': 'pending'})
    with db.tempEnv(connectionName='other'):
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            db.table('item').query().fetch()
    assert db.outcome == 'active'
    db.commit()
    assert observed(path) == [(1, 'pending')]
    with db.tempEnv(connectionName='other'):
        assert db.table('item').query().fetch()[0]['id'] == 1
        db.commit()


def test_raw_commands_keep_partition_checks_and_formula_results(tmp_path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(tmp_path / 'policies.db'), implementation='sqlite')
            table = db.schemas().schema('app').tables().table(
                'item', pkey='id', x_partition={'field': 'organization', 'current': 'organization'})
            columns = table.columns()
            for name in ('id', 'organization', 'quantity'):
                columns.column(name, dtype='I')
            table.virtual_columns().formulaColumn('doubled', sql_formula='$quantity * 2', dtype='I')
    db = AsqueelDb(Recipe)
    try:
        db.execute('CREATE TABLE app.item (id INTEGER PRIMARY KEY, organization INTEGER, quantity INTEGER)')
        db.commit()
        with pytest.raises(ValueError, match='partition'):
            db.table('item').raw_insert({'id': 1, 'quantity': 3})
        db.rollback()
        with db.tempEnv(organization=10):
            db.table('item').raw_insert({'id': 1, 'quantity': 3})
            db.commit()
            assert db.table('item').query(columns='$id, $doubled').fetch() == [{'id': 1, 'doubled': 6}]
            db.commit()
        with db.tempEnv(organization=20):
            assert db.table('item').raw_update({'id': 1, 'quantity': 9}).rowcount == 0
            assert db.table('item').raw_delete(1).rowcount == 0
            db.commit()
        with db.tempEnv(organization=10):
            assert db.table('item').query(columns='$quantity').fetch() == [{'quantity': 3}]
            db.commit()
    finally:
        db.close()
