"""Public hierarchical entries, legacy record outputs and real SQLite locks."""
import sqlite3

import pytest
from genro_bag import Bag
from genro_toolbox import NamedList

from asqueel import AsqueelDb, SqlDatabaseConfig, build_database, RecordNotFoundError, RecordMultipleRowsError
from asqueel.object_tree import DbModel


def recipe(filename):
    source = SqlDatabaseConfig()
    root = source.source.db('records', implementation='sqlite')
    root.connection('main', database=str(filename), options={'timeout': 0.05})
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    table.column('id', dtype='L')
    table.column('name', dtype='T')
    table.column('payload', dtype='X')
    table.formulaColumn('upper_name', sql_formula='upper($name)', static=True)
    return source


@pytest.fixture
def db(tmp_path):
    db = AsqueelDb(recipe(tmp_path / 'records.sqlite'))
    db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, payload TEXT)')
    db.execute('INSERT INTO item VALUES (:id,:name,:payload)',
               {'id': 0, 'name': 'first', 'payload': '<GenRoBag><value>hello</value></GenRoBag>'})
    db.execute('INSERT INTO item VALUES (1, :name, NULL)', {'name': 'second'})
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.parametrize('entry', [AsqueelDb, build_database, lambda s: s.render()])
def test_public_entries_share_one_model(entry, tmp_path):
    source = recipe(tmp_path / 'unused.sqlite')
    before = source.source.to_xml()
    with entry(source) as db:
        assert type(db.model) is DbModel
        table = db.table('app.item')
        assert table is db.model.table('app.item').dbtable
        assert table.columns['id'] is table.model.columns['id']
        assert table.query('$id').compiled.sql
        assert not db._connections
    assert source.source.to_xml() == before


def test_record_lazy_complete_snapshot_refresh_and_outputs(db):
    table = db.table('app.item')
    record = table.record(0)
    before = db._connection_state['execution_count']
    data = record.output('dict')
    assert set(data) == {'id', 'name', 'payload'}  # no static virtual columns
    assert data['id'] == 0
    assert isinstance(data['payload'], str)
    bag = record.output('record')
    assert isinstance(bag, Bag) and isinstance(bag['payload'], Bag)
    assert bag['payload.value'] == 'hello'
    assert bag.get_node('id').attr['dtype'] == 'L'
    assert db._connection_state['execution_count'] == before + 1
    data['name'] = 'local'
    assert record.output()['name'] == 'first'
    db.execute("UPDATE item SET name='changed' WHERE id=0")
    assert record.output()['name'] == 'first'
    assert record.refresh().output()['name'] == 'changed'
    assert db._connection_state['connection'].in_transaction


def test_missing_and_duplicate_records(db):
    table = db.table('app.item')
    with pytest.raises(RecordNotFoundError):
        table.record(99).output()
    assert table.record(99, ignoreMissing=True).output('dict') == {}
    assert len(table.record(99, ignoreMissing=True).output('record')) == 0
    with pytest.raises(RecordMultipleRowsError):
        table.record(where='$id>=0', ignoreMissing=True).output()


def test_record_and_query_locked_include_x(db):
    table = db.table('app.item')
    assert 'payload' in table.record(0, for_update=True, bagFields=False).output()
    rows = table.query('*', for_update=True, order_by='$id').fetch()
    assert type(rows[0]) is NamedList
    assert 'payload' in rows[0].keys()
    rows[0]['name'] = 'mutable'
    assert rows[0][1] == 'mutable'
    assert list(table.query('$id', for_update=True).fetch()[0].keys()) == ['id']


@pytest.mark.parametrize('already_open', [False, True])
@pytest.mark.parametrize('terminal', ['record', 'query'])
def test_sqlite_lock_blocks_other_writer_without_changing_rows(db, already_open, terminal):
    connection = db._connection_state['connection']
    trace = []
    connection.set_trace_callback(trace.append)
    if already_open:
        connection.execute('BEGIN')
    table = db.table('app.item')
    if terminal == 'record':
        table.record(0, for_update=True).output()
    else:
        table.query('$id', for_update=True).fetch()
    assert connection is db._connection_state['connection']
    assert connection.in_transaction
    assert ('BEGIN IMMEDIATE' in trace) != already_open
    assert any('WHERE 0' in sql for sql in trace) == already_open
    assert connection.execute('SELECT name FROM item WHERE id=0').fetchone()[0] == 'first'
    other = sqlite3.connect(connection.execute('PRAGMA database_list').fetchone()[2], isolation_level=None, timeout=0.05)
    try:
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            other.execute("UPDATE item SET name='other' WHERE id=0")
        db.rollback()
        other.execute("UPDATE item SET name='other' WHERE id=0")
    finally:
        other.close()


def test_record_uses_legacy_visibility_and_omits_static_virtuals(tmp_path):
    source = recipe(tmp_path / 'visibility.sqlite')
    table = source.source['db.packages.app.tables.item']
    table.attr.update(x_draft_field='draft', x_logical_deletion_field='deleted')
    table.column('draft', dtype='B')
    table.column('deleted', dtype='T')
    with AsqueelDb(source) as db:
        db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, payload TEXT, draft BOOL, deleted TEXT)')
        db.execute("INSERT INTO item VALUES (1,'hidden',NULL,TRUE,'deleted')")
        db.commit()
        assert db.table('app.item').query('$id').fetch() == []
        record = db.table('app.item').record(1, for_update=True).output()
        assert record['name'] == 'hidden'
        assert 'upper_name' not in record


def test_custom_table_class_survives_finalization(tmp_path):
    from asqueel import SqlTable

    class Item(SqlTable):
        def describe(self):
            return self.model.fullname

    source = recipe(tmp_path / 'custom.sqlite')
    source.source['db.packages.app.tables.item'].attr['x_table_class'] = Item
    with AsqueelDb(source) as db:
        assert isinstance(db.table('app.item'), Item)
        assert db.table('app.item').describe() == 'app.item'
        assert db.table('app.item') is db.model.table('app.item').dbtable


def test_model_only_render_does_not_resolve_connection_secrets():
    from genro_bag.resolvers import BagCbResolver

    source = SqlDatabaseConfig()
    root = source.source.db('offline', implementation='postgres')
    root.connection('main', database='offline', password=BagCbResolver(
        lambda: pytest.fail('Model rendering evaluated a connection password')))
    root.packages().package('app').table('item', pkey='id').column('id', dtype='L')
    assert type(source.render(mode='objects_tree')) is DbModel
