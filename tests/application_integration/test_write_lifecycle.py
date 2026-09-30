"""Shared lifecycle acceptance on both SQLite and PostgreSQL."""
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable, TransactionStateError
from tests.native_support import postgres_dsn


class Logic(SqlTable):
    def trigger_onInserting(self, record):
        self.db.currentEnv['events'].append('table-before')
        record['name'] = record['name'].strip()
    def trigger_onInserted(self, record):
        self.db.currentEnv['events'].append('table-after')
    def trigger_onUpdating(self, record, old_record=None):
        self.db.currentEnv['events'].append(('table-before', old_record['name']))
    def trigger_onUpdated(self, record, old_record=None):
        self.db.currentEnv['events'].append(('table-after', old_record['name']))
    def trigger_onDeleting(self, record):
        self.db.currentEnv['events'].append('table-before')
    def trigger_onDeleted(self, record):
        self.db.currentEnv['events'].append('table-after')


class IntegrationDb(AsqueelDb):
    def onWriting(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['events'].append(('before', event, raw))
    def onExecutingWrite(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['events'].append(('before-sql', event, raw))
    def _onDbChange(self, table, event, record, old_record=None, *, _raw=False):
        self.currentEnv['events'].append(('change', event, _raw))
        if table.model.name != 'audit':
            self.table('audit').raw_insert({'id': record['id'], 'name': event})
    def onWritten(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['events'].append(('after', event, raw))
        if self.currentEnv.get('fail_after') and table.model.name == 'item':
            raise ValueError('integration hook failed')
    def execute(self, query, sqlargs=None):
        if 'events' in self.currentEnv:
            self.currentEnv['events'].append('execute')
        return super().execute(query, sqlargs)


@pytest.fixture(params=['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)])
def database(request, tmp_path):
    backend = request.param
    physical_schema = 'life_' + uuid4().hex if backend == 'postgresql' else 'app'
    dsn = postgres_dsn() if backend == 'postgresql' else None
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db(conninfo=dsn) if dsn else root.db()
            if not dsn:
                db.connection(name=str(tmp_path / 'lifecycle.db'), implementation='sqlite')
            tables = db.schemas().schema('app', x_sql_schema=physical_schema).tables()
            for name in ('item', 'audit'):
                t = tables.table(name, pkey='id', **({'x_table_class': Logic} if name == 'item' else {})).columns()
                t.column('id', dtype='I')
                t.column('name', dtype='T')
    db = IntegrationDb(Recipe)
    if dsn:
        db.execute(f'CREATE SCHEMA "{physical_schema}"')
    for table in ('item', 'audit'):
        db.execute(f'CREATE TABLE "{physical_schema}"."{table}" (id INTEGER PRIMARY KEY, name TEXT)')
    db.commit()
    db.currentEnv['events'] = []
    try:
        yield db
    finally:
        db.rollback()
        if dsn:
            db.execute(f'DROP SCHEMA "{physical_schema}" CASCADE')
            db.commit()
        db.close()


def test_normal_and_raw_insertion_share_tracking_and_nested_execution(database):
    db = database
    record = {'id': 1, 'name': '  Ada  '}
    result = db.table('item').insert(record)
    assert result.rows == [{'id': 1, 'name': 'Ada'}]
    assert record['name'] == '  Ada  '
    events = db.currentEnv['events']
    assert events[:4] == [('before', 'I', False), 'table-before', ('before-sql', 'I', False), 'execute']
    assert events[-2:] == ['table-after', ('after', 'I', False)]
    assert ('change', 'I', False) in events and ('change', 'I', True) in events
    db.commit()
    events.clear()
    db.raw_insert('item', {'id': 2, 'name': '  raw  '})
    assert 'table-before' not in events and 'table-after' not in events
    assert ('change', 'I', True) in events
    db.commit()
    assert [row['name'] for row in db.table('item').query(order_by='$id').fetch()] == ['Ada', '  raw  ']
    assert len(db.table('audit').query().fetch()) == 2


def test_update_and_delete_track_raw_without_table_hooks(database):
    db = database
    db.table('item').insert({'id': 1, 'name': 'before'})
    db.commit()
    # Keep the fixture audit pkey available for each successive change.
    db.execute(f'DELETE FROM "{db.model.table("audit").physical_schema}"."audit"')
    db.commit()
    db.currentEnv['events'].clear()
    db.table('item').update({'id': 1, 'name': 'after'})
    assert ('table-before', 'before') in db.currentEnv['events']
    assert ('table-after', 'before') in db.currentEnv['events']
    db.rollback()
    db.currentEnv['events'].clear()
    db.table('item').raw_update({'id': 1, 'name': 'raw'})
    assert ('change', 'U', True) in db.currentEnv['events']
    assert not any(isinstance(x, tuple) and x[0].startswith('table-') for x in db.currentEnv['events'])
    db.rollback()
    db.currentEnv['events'].clear()
    db.table('item').raw_delete(1)
    assert ('change', 'D', True) in db.currentEnv['events']
    assert 'table-before' not in db.currentEnv['events']
    db.rollback()
    assert db.table('item').query().fetch()[0]['name'] == 'before'


def test_integration_hook_error_blocks_commit_for_normal_and_raw(database):
    db = database
    for raw in (False, True):
        db.currentEnv['fail_after'] = True
        with pytest.raises(ValueError, match='integration hook'):
            method = db.table('item').raw_insert if raw else db.table('item').insert
            method({'id': 1, 'name': 'discard'})
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.commit()
        db.rollback()
        db.currentEnv['fail_after'] = False
        assert db.table('item').query().fetch() == []
        assert db.table('audit').query().fetch() == []
        db.rollback()


def test_direct_sql_uses_driver_binding_and_same_environment(database):
    db = database
    with db.tempEnv(user="O'Reilly 50%"):
        result = db.execute("SELECT :env_user AS username, ':fake 50%' AS literal")
        assert result.rows == [{'username': "O'Reilly 50%", 'literal': ':fake 50%'}]
        db.commit()
