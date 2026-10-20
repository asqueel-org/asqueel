"""A file-free REPL session, plus transaction and model-reload boundaries."""
import csv
from io import StringIO

import pytest

from asqueel import AsqueelDb, MigrationError, SqlDatabaseConfig, TransactionStateError
from asqueel.contracts import UnsupportedFeatureError


def source(filename=':memory:', schema='shop'):
    model = SqlDatabaseConfig()
    root = model.source.db(implementation='sqlite')
    root.connection(name=filename, implementation='sqlite')
    table = root.packages().package('shop', sqlschema=schema).table('product', pkey='code')
    table.column('code', size=':10')
    table.column('name', size=':60')
    return model, table


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model, table = source()
    db = AsqueelDb(model)
    try:
        db.migrate()
        yield db, model, table
    finally:
        db.closeConnection()
    assert list(tmp_path.iterdir()) == [], 'An in-memory session wrote a database file'


def rows(table, columns='$code, $name'):
    return [dict(row) for row in table.query(columns=columns, order_by='$code').fetch()]


def test_repl_adds_columns_migrates_writes_and_imports_csv(session):
    db, model, definition = session
    product = db.table('shop.product')
    product.insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    assert rows(product) == [{'code': 'TEA', 'name': 'Tea'}]
    product.update({'name': 'Green tea'}, pkey='TEA')
    db.commit()
    original_connection = db._connection_state['connection']

    definition.column('category', size=':30')
    definition.column('stock', dtype='I')
    db.reload_model(model)
    plan = db.migration_plan()
    assert plan.commands.count('ADD COLUMN') == 2
    assert 'CREATE TABLE' not in plan.commands
    assert db.migrate().commands == plan.commands
    assert db.migration_plan().empty
    assert db._connection_state['connection'] is original_connection

    product = db.table('shop.product')
    assert rows(product, '$code, $name, $stock') == [
        {'code': 'TEA', 'name': 'Green tea', 'stock': None}]
    product.update({'category': 'Drinks', 'stock': 8}, pkey='TEA')
    data = StringIO('code,name,category,stock\nCOF,Coffee,Drinks,24\nMUG,Mug,Kitchen,12\n')
    for row in csv.DictReader(data):
        row['stock'] = int(row['stock'])
        product.insert(row)
    db.commit()
    assert [dict(row) for row in product.query(
        columns='$name, $stock', where='$category = :category', category='Drinks',
        order_by='$stock DESC').fetch()] == [
            {'name': 'Coffee', 'stock': 24}, {'name': 'Green tea', 'stock': 8}]


@pytest.mark.parametrize('operation', ['migration_plan', 'migrate', 'reload_model'])
def test_pending_write_is_not_committed_or_rolled_back(session, operation):
    db, model, _ = session
    product = db.table('shop.product')
    product.insert({'code': 'NEW', 'name': 'Pending'})
    args = (model,) if operation == 'reload_model' else ()
    with pytest.raises(TransactionStateError, match='pending work'):
        getattr(db, operation)(*args)
    assert rows(product) == [{'code': 'NEW', 'name': 'Pending'}]
    db.rollback()
    assert rows(product) == []


@pytest.mark.parametrize('queue', ['deferToCommit', 'deferAfterCommit', 'deferredRaise'])
def test_deferred_work_is_not_lost(session, queue):
    db, _, _ = session
    called = []
    value = ValueError('queued') if queue == 'deferredRaise' else lambda: called.append(True)
    getattr(db, queue)(value)
    with pytest.raises(TransactionStateError, match='pending work'):
        db.migrate()
    assert not called
    db.rollback()
    assert db.migration_plan().empty


def test_failed_ddl_rolls_back_all_changes_and_keeps_connection_alive(session):
    db, model, definition = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    definition.column('category', size=':30')
    definition.column('stock', dtype='I', notnull=True)
    db.reload_model(model)
    with pytest.raises(MigrationError):
        db.migrate()  # SQLite cannot add NOT NULL without a default to populated rows.
    cursor = db.execute('PRAGMA shop.table_info(shop_product)')
    assert [row[1] for row in cursor.fetchall()] == ['code', 'name']
    cursor.close()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
    db.commit()
    assert db.migration_plan().commands.count('ADD COLUMN') == 2


@pytest.mark.parametrize('terminal', ['fetch', 'fetchRecord', 'count', 'sql_update', 'sql_delete'])
def test_reload_invalidates_old_tables_and_cached_queries(session, terminal):
    db, model, definition = session
    product = db.table('shop.product')
    product.insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    query = product.query(columns='$code, $name', order_by='$code')
    query.fetchRecord()  # Populate the ordered-single-row compilation cache too.
    query.compiled
    db.commit()
    definition.column('stock', dtype='I')
    db.reload_model(model)
    db.migrate()
    with pytest.raises(UnsupportedFeatureError, match='not bound'):
        product.insert({'code': 'BAD', 'name': 'stale'})
    with pytest.raises(UnsupportedFeatureError, match='not bound'):
        getattr(query, terminal)(*({'name': 'stale'},) if terminal == 'sql_update' else ())


def test_invalid_replacement_keeps_original_graph_and_rows(session):
    db, _, _ = session
    product = db.table('shop.product')
    product.insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    changed, _ = source(filename='another.db')
    with pytest.raises(MigrationError, match='connection settings'):
        db.reload_model(changed)
    changed, _ = source(schema='another_schema')
    with pytest.raises(MigrationError, match='SQL schemas'):
        db.reload_model(changed)
    assert db.table('shop.product') is product
    assert rows(product) == [{'code': 'TEA', 'name': 'Tea'}]


def test_unsupported_change_does_not_close_or_modify_memory_database(session):
    db, _, _ = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    replacement = SqlDatabaseConfig()
    root = replacement.source.db(implementation='sqlite')
    root.connection(name=':memory:', implementation='sqlite')
    table = root.packages().package('shop', sqlschema='shop').table('product', pkey='code')
    table.column('code', size=':10')
    table.column('name', dtype='I')
    db.reload_model(replacement)
    assert db.migration_plan().skipped
    with pytest.raises(MigrationError, match='cannot apply'):
        db.migrate()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]


def test_secondary_connections_cannot_be_migrated_or_reloaded(session):
    db, model, _ = session
    with db.tempEnv(connectionName='secondary'):
        with pytest.raises(MigrationError, match='main SQLite connection'):
            db.migrate()
        cursor = db.execute('SELECT 1')
        cursor.close()
        db.commit()
    with pytest.raises(MigrationError, match='single main connection'):
        db.reload_model(model)
    assert db.migration_plan().empty


def test_reload_does_not_accept_file_backed_databases(tmp_path):
    model, _ = source(str(tmp_path / 'catalog.db'))
    db = AsqueelDb(model)
    try:
        with pytest.raises(MigrationError, match='only supported for SQLite :memory:'):
            db.reload_model(model)
        assert not list(tmp_path.iterdir())
    finally:
        db.closeConnection()


def test_two_memory_handles_are_independent_and_close_discards_data(session):
    db, model, _ = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    other = AsqueelDb(model)
    try:
        assert not other.migration_plan().empty
        other.migrate()
        assert rows(other.table('shop.product')) == []
    finally:
        other.closeConnection()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
    db.closeConnection()
    assert not db.migration_plan().empty
    db.migrate()
    assert rows(db.table('shop.product')) == []


def test_main_schema_uses_memory_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model, _ = source(schema='main')
    db = AsqueelDb(model)
    try:
        db.migrate()
        db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
        db.commit()
        assert db.migration_plan().empty
        assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
        assert not list(tmp_path.iterdir())
    finally:
        db.closeConnection()
