"""A file-free REPL session, plus transaction and model-reload boundaries."""
import csv
from io import StringIO

import pytest

from asqueel import AsqueelDb, MigrationError, SqlDatabaseConfig, TransactionStateError
from asqueel.contracts import UnsupportedFeatureError
from tests.package_layout_support import write_layout


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
    db = AsqueelDb(model).session()
    try:
        db.migrate()
        yield db, model, table
    finally:
        db.closeConnection()
        db.shared.close()
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
    db.reloadModel(model)
    plan = db.migration_plan()
    assert plan['sql'].count('ADD COLUMN') == 2
    assert 'CREATE TABLE' not in plan['sql']
    assert db.migrate()['sql'] == plan['sql']
    assert db.migration_plan()['empty']
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


@pytest.mark.parametrize('operation', ['migration_plan', 'migrate', 'reloadModel'])
def test_pending_write_is_not_committed_or_rolled_back(session, operation):
    db, model, _ = session
    product = db.table('shop.product')
    product.insert({'code': 'NEW', 'name': 'Pending'})
    args = (model,) if operation == 'reloadModel' else ()
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
    assert db.migration_plan()['empty']


def test_failed_ddl_rolls_back_all_changes_and_keeps_connection_alive(session):
    db, model, definition = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    definition.column('category', size=':30')
    definition.column('stock', dtype='I', notnull=True)
    db.reloadModel(model)
    with pytest.raises(MigrationError):
        db.migrate()  # SQLite cannot add NOT NULL without a default to populated rows.
    cursor = db.execute('PRAGMA shop.table_info(shop_product)')
    assert [row[1] for row in cursor.fetchall()] == ['code', 'name']
    cursor.close()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
    db.commit()
    assert db.migration_plan()['sql'].count('ADD COLUMN') == 2


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
    db.reloadModel(model)
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
        db.reloadModel(changed)
    changed, _ = source(schema='another_schema')
    with pytest.raises(MigrationError, match='SQL schemas'):
        db.reloadModel(changed)
    assert db.table('shop.product') is product
    assert rows(product) == [{'code': 'TEA', 'name': 'Tea'}]


def test_a_failed_model_build_keeps_the_original_model(session, monkeypatch):
    from asqueel.object_tree import DbModel
    db, _, _ = session
    product = db.table('shop.product')
    model = db.model

    def broken(self, fragment):
        raise RuntimeError('build failed')

    monkeypatch.setattr(DbModel, 'build', broken)
    changed, _ = source()
    with pytest.raises(RuntimeError, match='build failed'):
        db.reloadModel(changed)
    assert db.model is model
    assert db.table('shop.product') is product


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
    db.reloadModel(replacement)
    assert db.migration_plan()['skipped']
    with pytest.raises(MigrationError, match='cannot apply'):
        db.migrate()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]


def test_secondary_connections_cannot_be_migrated_or_reloaded(session):
    db, model, _ = session
    # A :memory: database lends its connection to one session: a secondary one cannot open.
    with db.tempEnv(connectionName='secondary'):
        with pytest.raises(TransactionStateError, match='one session at a time'):
            db.migrate()
        with pytest.raises(TransactionStateError, match='one session at a time'):
            db.execute('SELECT 1')
    with pytest.raises(TransactionStateError, match='one session at a time'):
        db.session('secondary')
    db.reloadModel(model)
    assert db.migration_plan()['empty']


def test_reload_does_not_accept_file_backed_databases(tmp_path):
    model, _ = source(str(tmp_path / 'catalog.db'))
    db = AsqueelDb(model)
    try:
        with pytest.raises(MigrationError, match='only supported for SQLite :memory:'):
            db.reloadModel(model)
        assert not list(tmp_path.iterdir())
    finally:
        db.closeConnection()


def test_two_memory_handles_are_independent_and_keep_data_until_the_database_closes(session):
    db, model, _ = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    other = AsqueelDb(model).session()
    try:
        assert not other.migration_plan()['empty']
        other.migrate()
        assert rows(other.table('shop.product')) == []
    finally:
        other.closeConnection()
        other.shared.close()
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
    # The :memory: connection belongs to the shared database: closeConnection keeps it.
    db.closeConnection()
    assert db.migration_plan()['empty']
    assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]


def test_main_schema_uses_memory_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model, _ = source(schema='main')
    db = AsqueelDb(model).session()
    try:
        db.migrate()
        db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
        db.commit()
        assert db.migration_plan()['empty']
        assert rows(db.table('shop.product')) == [{'code': 'TEA', 'name': 'Tea'}]
        assert not list(tmp_path.iterdir())
    finally:
        db.closeConnection()
        db.shared.close()



def shop(related=False):
    model = SqlDatabaseConfig()
    root = model.source.db(implementation='sqlite')
    root.connection(name=':memory:', implementation='sqlite')
    pkg = root.packages().package('shop', sqlschema='shop')
    product = pkg.table('product', pkey='code')
    product.column('code', size=':10')
    product.column('name', size=':60')
    if related:
        category = pkg.table('category', pkey='code')
        category.column('code', size=':10')
        category.column('name', size=':30')
        product.column('category_code', size=':10').relation('shop.category.code')
    return model


def test_a_relation_added_to_an_existing_table_migrates_without_the_constraint(session):
    db, _, _ = session
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    db.reloadModel(shop(related=True))
    with pytest.raises(MigrationError, match='foreign key'):
        db.migrate()
    db.migrate(foreignKeys=False)
    db.table('shop.category').insert({'code': 'DR', 'name': 'Drinks'})
    db.table('shop.product').update({'category_code': 'DR'}, pkey='TEA')
    db.commit()
    assert rows(db.table('shop.product'), '$code, @category_code.name') == [
        {'code': 'TEA', '_category_code_name': 'Drinks'}]


PRODUCT = '''
class Table:
    def config_db(self, pkg):
        product = pkg.table('product', pkey='code')
        product.column('code', size=':10')
        product.column('name', size=':60')
'''

LOUD = PRODUCT + '''
    def formulaColumn_label(self):
        return dict(name='label', sql_formula='upper($name)', dtype='T')
'''

QUIET = PRODUCT + '''
    def formulaColumn_label(self):
        return dict(name='label', sql_formula='lower($name)', dtype='T')
'''


def layout_shop(folder, product):
    """``shop()`` whose product comes from the package folder ``folder``; the session's directory stays empty."""
    model = SqlDatabaseConfig()
    root = model.source.db(implementation='sqlite')
    root.connection(name=':memory:', implementation='sqlite')
    root.packages().package('shop', sqlschema='shop', path=write_layout(folder, product=product))
    return model


def test_reload_rereads_dynamic_formula_columns(session, tmp_path_factory):
    db, _, _ = session
    db.reloadModel(layout_shop(tmp_path_factory.mktemp('loud'), LOUD))
    db.table('shop.product').insert({'code': 'TEA', 'name': 'Tea'})
    db.commit()
    assert rows(db.table('shop.product'), '$code, $label') == [{'code': 'TEA', 'label': 'TEA'}]
    db.commit()
    db.reloadModel(layout_shop(tmp_path_factory.mktemp('quiet'), QUIET))
    assert rows(db.table('shop.product'), '$code, $label') == [{'code': 'TEA', 'label': 'tea'}]
