"""Public hierarchical entries, fetchRecord reads and real SQLite locks."""
import sqlite3

import pytest
from genro_toolbox import NamedList

from asqueel import AsqueelDb, SqlDatabaseConfig, RecordNotFoundError, RecordMultipleRowsError
from asqueel.object_tree import DbModel
from tests.package_layout_support import write_layout


def recipe(filename):
    source = SqlDatabaseConfig()
    root = source.source.db('records', implementation='sqlite')
    root.connection('main', database=str(filename)).options().driver(timeout=0.05)
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
        db.closeConnection()


@pytest.mark.parametrize('entry', [AsqueelDb])
def test_public_entries_share_one_model(entry, tmp_path):
    source = recipe(tmp_path / 'unused.sqlite')
    before = source.source.to_xml()
    db = entry(source)
    try:
        assert type(db.model) is DbModel
        table = db.table('app.item')
        assert table is db.model.table('app.item').dbtable
        assert table.columns['id'] is table.model.columns['id']
        assert table.query('$id').compiled.sql
        assert not db._connections
    finally:
        db.closeConnection()
    assert source.source.to_xml() == before


def test_fetch_record_reads_the_complete_row_at_every_call(db):
    # The Bag output of the removed record() has no replacement in this release.
    table = db.table('app.item')
    query = table.query('$id,$name,$payload', where='$id=0')
    before = db._connection_state['execution_count']
    row = query.fetchRecord()
    assert dict(row) == {'id': 0, 'name': 'first', 'payload': '<GenRoBag><value>hello</value></GenRoBag>'}
    assert db._connection_state['execution_count'] == before + 1
    db.execute("UPDATE item SET name='changed' WHERE id=0")
    assert query.fetchRecord()['name'] == 'changed'
    assert db._connection_state['connection'].in_transaction


def test_missing_and_duplicate_records(db):
    # The Bag output of the removed record() has no replacement in this release.
    table = db.table('app.item')
    with pytest.raises(RecordNotFoundError):
        table.query(where='$id=99').fetchRecord()
    assert table.query(where='$id=99').fetchRecord(ignoreMissing=True) is None
    with pytest.raises(RecordMultipleRowsError):
        table.query(where='$id>=0').fetchRecord(ignoreMissing=True)


def test_locked_queries_include_x(db):
    table = db.table('app.item')
    assert 'payload' in table.query('*', where='$id=0', for_update=True).fetchRecord().keys()
    rows = table.query('*', for_update=True, order_by='$id').fetch()
    assert type(rows[0]) is NamedList
    assert 'payload' in rows[0].keys()
    rows[0]['name'] = 'mutable'
    assert rows[0][1] == 'mutable'
    assert list(table.query('$id', for_update=True).fetch()[0].keys()) == ['id']


@pytest.mark.parametrize('already_open', [False, True])
@pytest.mark.parametrize('terminal', ['fetchRecord', 'fetch'])
def test_sqlite_lock_blocks_other_writer_without_changing_rows(db, already_open, terminal):
    connection = db._connection_state['connection']
    trace = []
    connection.set_trace_callback(trace.append)
    if already_open:
        connection.execute('BEGIN')
    table = db.table('app.item')
    if terminal == 'fetchRecord':
        table.query('$id', where='$id=0', for_update=True).fetchRecord()
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


def test_fetch_record_reads_hidden_rows_with_the_visibility_filters_off(tmp_path):
    source = recipe(tmp_path / 'visibility.sqlite')
    table = source.source['db.packages.app.tables.item']
    table.attr.update(draftField='draft', logicalDeletionField='deleted')
    table.column('draft', dtype='B')
    table.column('deleted', dtype='T')
    db = AsqueelDb(source)
    try:
        db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT, payload TEXT, draft BOOL, deleted TEXT)')
        db.execute("INSERT INTO item VALUES (1,'hidden',NULL,TRUE,'deleted')")
        db.commit()
        assert db.table('app.item').query('$id').fetch() == []
        record = db.table('app.item').query('*', where='$id=1', for_update=True, exclude_draft=False,
                                             exclude_logical_deleted=False).fetchRecord()
        assert record['name'] == 'hidden'
    finally:
        db.closeConnection()


ITEM = '''
class Table:
    def config_db(self, pkg):
        table = pkg.table('item', pkey='id')
        table.column('id', dtype='L')
        table.column('name', dtype='T')

    def describe(self):
        return self.model.fullname
'''


def test_custom_table_class_survives_finalization(tmp_path):
    source = SqlDatabaseConfig()
    root = source.source.db('records', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'custom.sqlite'))
    root.packages().package('app', sqlschema='main', sqlprefix=False,
                            path=write_layout(tmp_path / 'app', item=ITEM))
    db = AsqueelDb(source)
    try:
        assert [cls.__name__ for cls in type(db.table('app.item')).__mro__[:3]] == ['item', 'Table', 'SqlTable']
        assert db.table('app.item').describe() == 'app.item'
        assert db.table('app.item') is db.model.table('app.item').dbtable
    finally:
        db.closeConnection()
