"""SQLite exercises the same application lifecycle, not a parallel API."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, TransactionStateError
from asqueel.cli import run_migration
from tests.package_layout_support import write_layout


ITEM = '''
class Table:
    def config_db(self, pkg):
        columns = pkg.tables().table('item', pkey='id').columns()
        columns.column('id', dtype='I')
        columns.column('name', dtype='T')

    def trigger_onInserting(self, record):
        record['name'] = record['name'].strip()
    def trigger_onInserted(self, record):
        if record['name'] == 'fail':
            raise ValueError('hook failure')
    def trigger_onUpdating(self, record, old_record=None):
        record['name'] += '!'
'''


def recipe(path):
    layout = write_layout(path.parent / 'app', item=ITEM)

    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite').options().driver(timeout=0.1)
            db.packages().package('app', sqlschema='app', sqlprefix=False, path=layout)
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
        db.closeConnection()


def observed(path):
    with sqlite3.connect(path.with_name('app.db')) as connection:
        return connection.execute('SELECT id, name FROM item ORDER BY id').fetchall()


def test_normal_and_raw_commands_share_execute_and_explicit_commit(database):
    db, path = database
    table = db.table('app.item')
    assert table.insert({'id': 1, 'name': '  Ada  '}) == {'id': 1, 'name': 'Ada'}
    assert observed(path) == []
    db.commit()
    assert observed(path) == [(1, 'Ada')]
    table.update({'id': 1, 'name': 'Grace'})
    assert table.query().fetch()[0]['name'] == 'Grace!'
    table.sql_update({'id': 1, 'name': 'raw'})
    table.sql_insert({'id': 2, 'name': ' fail '})
    db.commit()
    assert observed(path) == [(1, 'raw'), (2, ' fail ')]
    table.sql_delete({'id': 1})
    table.delete({'id': 2})
    db.rollback()
    assert len(observed(path)) == 2


def test_hook_failure_blocks_commit_and_rollback_restores_usability(database):
    db, path = database
    with pytest.raises(ValueError, match='hook failure'):
        db.table('app.item').insert({'id': 1, 'name': 'fail'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()
    db.rollback()
    assert observed(path) == []
    db.table('app.item').insert({'id': 2, 'name': 'ok'})
    db.commit()
    assert observed(path) == [(2, 'ok')]


def test_parameters_environment_percent_literals_and_sql_error(database):
    db, path = database
    with db.tempEnv(user="O'Reilly"):
        result = db.execute("SELECT :env_user AS name, '50% :literal' AS label")
        assert [dict(row) for row in result.fetchall()] == [{'name': "O'Reilly", 'label': '50% :literal'}]
    db.rollback()
    db.execute('INSERT INTO app.item VALUES (:id, :name)', {'id': 1, 'name': 'ok'})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('INSERT INTO app.item VALUES (:id, :name)', {'id': 1, 'name': 'duplicate'})
    assert observed(path) == []
    db.table('app.item').sql_insert({'id': 2, 'name': 'retry'})
    db.commit()


def test_threads_and_named_connections_use_same_files_with_independent_state(database):
    db, path = database
    def worker():
        try:
            assert db.currentEnv == {}
            with db.tempEnv(connectionName='worker', user='worker'):
                db.table('app.item').sql_insert({'id': 1, 'name': 'worker'})
                db.commit()
        finally:
            db.closeConnection()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()
    assert observed(path) == [(1, 'worker')]
    assert db.currentEnv == {}
    with db.tempEnv(connectionName='other'):
        db.table('app.item').sql_update({'id': 1, 'name': 'other'})
        db.rollback()
    assert observed(path) == [(1, 'worker')]


def test_sqlite_cli_reuses_existing_migrator_and_file_layout(tmp_path):
    path = tmp_path / 'sample.db'
    db = AsqueelDb(recipe(path))
    try:
        assert run_migration(db, 'apply') == 0
        db.table('app.item').insert({'id': 1, 'name': 'migrated'})
        db.commit()
        assert observed(path) == [(1, 'migrated')]
        assert db.migration_plan()['empty']
    finally:
        db.closeConnection()


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
        assert [dict(row) for row in rows] == [{'id': 10, 'customer': 'Ada', 'description': 'Example'}]
        db.commit()
        assert (tmp_path / 'contacts.db').exists()
        assert (tmp_path / 'sales.db').exists()
    finally:
        db.closeConnection()


def test_another_named_connection_reads_committed_state_without_losing_first_transaction(database):
    db, path = database
    db.table('app.item').sql_insert({'id': 1, 'name': 'pending'})
    with db.tempEnv(connectionName='other'):
        assert db.table('app.item').query().fetch() == []
    assert db._connection_state['pending']
    db.commit()
    assert observed(path) == [(1, 'pending')]
    with db.tempEnv(connectionName='other'):
        assert db.table('app.item').query().fetch()[0]['id'] == 1
        db.commit()


def partitioned(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite')
            table = db.packages().package('app', sqlschema='app', sqlprefix=False).tables().table(
                'item', pkey='id', partition_organization='organization')
            columns = table.columns()
            for name in ('id', 'organization', 'quantity'):
                columns.column(name, dtype='I')
            table.virtual_columns().formulaColumn('doubled', sql_formula='$quantity * 2', dtype='I')
    db = AsqueelDb(Recipe)
    db.execute('CREATE TABLE app.item (id INTEGER PRIMARY KEY, organization INTEGER, quantity INTEGER)')
    db.commit()
    return db


def test_raw_commands_keep_partition_checks_and_formula_results(tmp_path):
    db = partitioned(tmp_path / 'policies.db')
    try:
        with db.tempEnv(current_organization=10):
            db.table('app.item').sql_insert({'id': 1, 'organization': 10, 'quantity': 3})
            db.commit()
            assert [dict(row) for row in db.table('app.item').query(columns='$id, $doubled').fetch()] == [{'id': 1, 'doubled': 6}]
            db.commit()
        with db.tempEnv(current_organization=20):
            assert db.table('app.item').query(where='$id = :id', id=1).sql_update({'quantity': 9}) == 0
            assert db.table('app.item').query(where='$id = :id', id=1).sql_delete() == 0
            db.commit()
        with db.tempEnv(current_organization=10):
            assert [dict(row) for row in db.table('app.item').query(columns='$quantity').fetch()] == [{'quantity': 3}]
            db.commit()
    finally:
        db.closeConnection()


@pytest.mark.xfail(strict=True, reason='asqueel#15: sql_insert neither refuses nor fills the partition field')
def test_raw_insert_refuses_and_fills_the_partition(tmp_path):
    db = partitioned(tmp_path / 'policies.db')
    try:
        with pytest.raises(ValueError, match='partition'):
            db.table('app.item').sql_insert({'id': 1, 'quantity': 3})
        db.rollback()
        with db.tempEnv(current_organization=10):
            db.table('app.item').sql_insert({'id': 1, 'quantity': 3})
            db.commit()
            assert [dict(row) for row in db.table('app.item').query(columns='$id, $organization').fetch()] == [{'id': 1, 'organization': 10}]
            db.commit()
    finally:
        db.closeConnection()
