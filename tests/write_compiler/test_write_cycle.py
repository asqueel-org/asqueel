"""The insert, update and delete cycle on the hierarchical model, as GenroPy WriteMixin."""
from uuid import uuid4

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig, SqlTable
from asqueel.application_table import RecordNotFoundError
from asqueel.configuration import _owned_handler
from asqueel.errors import DeleteException, ProtectUpdateException, SaveException
from tests.native_support import postgres_dsn


class Table(SqlTable):
    """Application table that records the hook calls."""

    def log(self, *event):
        self.db.currentEnv.setdefault('events', []).append(event)


class Parent(Table):
    def trigger_upper(self, record, fldname, tblname, **kwargs):
        self.log('field', fldname, tblname, 'old_record' in kwargs)
        if record.get(fldname):
            record[fldname] = record[fldname].upper()

    def trigger_onInserting(self, record):
        self.log('onInserting', record.get('id') is not None)

    def trigger_onInserted(self, record):
        self.log('onInserted', record['state'])
        if record['name'] == 'WITH CHILD':
            self.db.table('sales.child').insert({'id': 'c-' + record['id'], 'parent_id': record['id']})

    def trigger_onUpdating(self, record, old_record=None):
        self.log('onUpdating', dict(old_record or {}).get('name'))

    def trigger_onUpdated(self, record, old_record=None):
        self.log('onUpdated')

    def trigger_onDeleting(self, record):
        self.log('onDeleting', record.get('name'))

    def trigger_onDeleted(self, record):
        self.log('onDeleted')

    def protect_update(self, record, old_record=None):
        if record.get('name') == 'FORBIDDEN':
            raise self.exception('protect_update', record=record, msg='name is reserved')


class Child(Table):
    def trigger_onInserted(self, record):
        parent = self.currentTrigger.parent
        self.log('child onInserted', parent.event, parent.table)

    def trigger_onDeleted(self, record):
        self.log('child onDeleted', record['id'])


def recipe(implementation, conninfo=None, path=None, schema=None):
    source = SqlDatabaseConfig()
    kwargs = {'implementation': implementation}
    if conninfo:
        kwargs['conninfo'] = conninfo
    db = source.source.db('cycle', **kwargs)
    if path:
        db.connection(name=str(path), implementation='sqlite')
    pkg = db.packages().package('sales', sqlschema=schema, sqlprefix=True)
    parent = pkg.table('parent', pkey='id', x_table_class=Parent)
    parent.column('id', size=':22')
    parent.column('name', onInserting='upper', onUpdating='upper')
    parent.column('state', sql_default="'new'")
    child = pkg.table('child', pkey='id', x_table_class=Child)
    child.column('id', size=':22')
    child.column('parent_id', size=':22').relation('sales.parent.id', onDelete='cascade', onUpdate='cascade')
    kid = pkg.table('kid', pkey='id', x_table_class=Table)
    kid.column('id', size=':22')
    kid.column('parent_id', size=':22').relation('sales.parent.id', onDelete='setnull')
    ref = pkg.table('ref', pkey='id', x_table_class=Table)
    ref.column('id', size=':22')
    ref.column('parent_id', size=':22').relation('sales.parent.id', onDelete='raise:Parent still used by %(reltable)s')
    lock = pkg.table('locked', pkey='id', x_table_class=Table, deletable=False)
    lock.column('id', size=':22')
    return source


DDL = (
    "CREATE TABLE {s}sales_parent (id TEXT PRIMARY KEY, name TEXT, state TEXT DEFAULT 'new')",
    'CREATE TABLE {s}sales_child (id TEXT PRIMARY KEY, parent_id TEXT)',
    'CREATE TABLE {s}sales_kid (id TEXT PRIMARY KEY, parent_id TEXT)',
    'CREATE TABLE {s}sales_ref (id TEXT PRIMARY KEY, parent_id TEXT)',
    'CREATE TABLE {s}sales_locked (id TEXT PRIMARY KEY)',
)


@pytest.fixture(params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
def db(request, tmp_path):
    if request.param == 'sqlite':
        source, prefix = recipe('sqlite', path=tmp_path / 'cycle.db'), ''
    else:
        schema = 'wcy_' + uuid4().hex[:8]
        source, prefix = recipe('postgres', conninfo=postgres_dsn(), schema=schema), f'"{schema}".'
    database = SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))
    try:
        if prefix:
            database.execute(f'CREATE SCHEMA {prefix[:-1]}')
        for statement in DDL:
            database.execute(statement.format(s=prefix))
        database.commit()
        database.prefix = prefix
        try:
            yield database
        finally:
            database.rollback()
            if prefix:
                database.execute(f'DROP SCHEMA {prefix[:-1]} CASCADE')
                database.commit()
    finally:
        database.closeConnection()


def events(db):
    return db.currentEnv.pop('events', [])


def rows(db, table, columns='id'):
    return [dict(r) for r in db.execute(f'SELECT {columns} FROM {db.prefix}sales_{table} ORDER BY id').rows]


def test_insert_runs_the_legacy_order_and_returns_the_modified_record(db):
    record = {'name': 'ada'}
    assert db.table('sales.parent').insert(record) is record
    assert len(record['id']) == 22 and record['id'].startswith('Z')  # checkPkey: genro_toolbox get_uuid
    assert record['name'] == 'ADA'  # field trigger before the table trigger
    assert record['state'] == 'new'  # RETURNING of the SQL default
    assert events(db) == [('field', 'name', 'sales.parent', False), ('onInserting', True), ('onInserted', 'new')]


def test_nested_write_sees_its_parent_on_the_trigger_stack(db):
    db.table('sales.parent').insert({'id': 'p1', 'name': 'with child'})
    assert ('child onInserted', 'insert', 'sales.parent') in events(db)
    assert rows(db, 'child', 'id, parent_id') == [{'id': 'c-p1', 'parent_id': 'p1'}]
    assert db.currentTrigger is None


def test_update_writes_present_keys_and_passes_the_caller_old_record(db):
    table = db.table('sales.parent')
    table.insert({'id': 'p1', 'name': 'ada'})
    events(db)
    record = {'id': 'p1', 'name': 'bob'}
    assert table.update(record, old_record={'id': 'p1', 'name': 'ADA'}) is record
    assert events(db) == [('field', 'name', 'sales.parent', True), ('onUpdating', 'ADA'), ('onUpdated',)]
    assert rows(db, 'parent', 'id, name, state') == [{'id': 'p1', 'name': 'BOB', 'state': 'new'}]


def test_protect_update_refuses_with_a_message_for_the_user(db):
    table = db.table('sales.parent')
    table.insert({'id': 'p1', 'name': 'ada'})
    with pytest.raises(ProtectUpdateException, match='p1 in table sales.parent is not updatable: name is reserved'):
        table.update({'id': 'p1', 'name': 'FORBIDDEN'}, old_record={'id': 'p1'})


def test_update_cascades_a_changed_key_to_the_children(db):
    table = db.table('sales.parent')
    table.insert({'id': 'p1', 'name': 'with child'})
    table.update({'id': 'p2'}, old_record={'id': 'p1'})
    assert rows(db, 'parent') == [{'id': 'p2'}]
    assert rows(db, 'child', 'id, parent_id') == [{'id': 'c-p1', 'parent_id': 'p2'}]


def test_delete_by_missing_key_string_returns_quietly(db):
    assert db.table('sales.parent').delete('missing') is None
    assert events(db) == []


def test_delete_reloads_an_incomplete_record_and_runs_related_actions(db):
    table = db.table('sales.parent')
    table.insert({'id': 'p1', 'name': 'with child'})
    db.table('sales.kid').insert({'id': 'k1', 'parent_id': 'p1'})
    events(db)
    table.delete({'id': 'p1'})
    log = events(db)
    assert log[0] == ('onDeleting', 'WITH CHILD')  # the record was reloaded
    assert ('child onDeleted', 'c-p1') in log and log.index(('child onDeleted', 'c-p1')) < log.index(('onDeleted',))
    assert rows(db, 'parent') == [] and rows(db, 'child') == []
    assert rows(db, 'kid', 'id, parent_id') == [{'id': 'k1', 'parent_id': None}]


def test_delete_of_a_complete_but_missing_record_is_an_error(db):
    with pytest.raises(RecordNotFoundError):
        db.table('sales.parent').delete({'id': 'zz', 'name': None, 'state': None})


def test_not_deletable_table_refuses(db):
    db.table('sales.locked').insert({'id': 'l1'})
    with pytest.raises(DeleteException, match='cannot be deleted'):
        db.table('sales.locked').delete('l1')


def test_raise_action_refuses_the_delete_with_its_message(db):
    db.table('sales.parent').insert({'id': 'p1', 'name': 'ada'})
    db.table('sales.ref').insert({'id': 'r1', 'parent_id': 'p1'})
    with pytest.raises(DeleteException, match='cannot be deleted: Parent still used by sales.ref'):
        db.table('sales.parent').delete('p1')


def test_update_without_old_record_on_a_table_with_onupdate_is_an_error(db):
    db.table('sales.parent').insert({'id': 'p1', 'name': 'ada'})
    with pytest.raises(ValueError, match='requires old_record'):
        db.table('sales.parent').update({'id': 'p1', 'name': 'bob'})


def test_save_exception_keeps_the_legacy_caption():
    error = SaveException('Record referenced in table %(reltable)s', tablename='sales.parent',
                          rowcaption='p1', reltable='sales.child')
    assert str(error) == 'The record p1 in table sales.parent cannot be saved: Record referenced in table sales.child'
