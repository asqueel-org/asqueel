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
        if self.db.currentEnv.get('fail_after'):
            self.db.table('app.audit').insert({'id': record['id'], 'name': 'I'})
            raise ValueError('table trigger failed')
    def trigger_onUpdating(self, record, old_record=None):
        self.db.currentEnv['events'].append(('table-before', old_record['name']))
    def trigger_onUpdated(self, record, old_record=None):
        self.db.currentEnv['events'].append(('table-after', old_record['name']))
    def trigger_onDeleting(self, record):
        self.db.currentEnv['events'].append('table-before')
    def trigger_onDeleted(self, record):
        self.db.currentEnv['events'].append('table-after')


class IntegrationDb(AsqueelDb):
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
    assert db.table('app.item').insert(record) is record
    assert record['name'] == 'Ada'
    events = db.currentEnv['events']
    assert events == ['table-before', 'execute', 'table-after']
    db.commit()
    events.clear()
    db.table('app.item').sql_insert({'id': 2, 'name': '  raw  '})
    assert events == ['execute']
    db.commit()
    assert [row['name'] for row in db.table('app.item').query(order_by='$id').fetch()] == ['Ada', '  raw  ']


def test_update_and_delete_track_raw_without_table_hooks(database):
    db = database
    table = db.table('app.item')
    table.insert({'id': 1, 'name': 'before'})
    db.commit()
    old = table.record(1, for_update=True).output('dict')
    db.currentEnv['events'].clear()
    table.update({'id': 1, 'name': 'after'}, old_record=old)
    assert ('table-before', 'before') in db.currentEnv['events']
    assert ('table-after', 'before') in db.currentEnv['events']
    db.rollback()
    db.currentEnv['events'].clear()
    assert table.sql_update({'id': 1, 'name': 'raw'}) is None
    assert db.currentEnv['events'] == ['execute']
    db.rollback()
    db.currentEnv['events'].clear()
    assert table.sql_delete({'id': 1}) is None
    assert db.currentEnv['events'] == ['execute']
    db.rollback()
    assert table.query().fetch()[0]['name'] == 'before'


def test_integration_hook_error_blocks_commit_for_normal_and_raw(database):
    db = database
    db.currentEnv['fail_after'] = True
    with pytest.raises(ValueError, match='table trigger'):
        db.table('app.item').insert({'id': 1, 'name': 'discard'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()
    db.rollback()
    db.currentEnv['fail_after'] = False
    assert db.table('app.item').query().fetch() == []
    assert db.table('app.audit').query().fetch() == []


def test_direct_sql_uses_driver_binding_and_same_environment(database):
    db = database
    with db.tempEnv(user="O'Reilly 50%"):
        literal = r"\:fake 50%%" if db.dialect.name == 'postgresql' else r"\:fake 50%"
        result = db.execute(f"SELECT :env_user AS username, '{literal}' AS literal")
        assert [dict(row) for row in result.rows] == [{'username': "O'Reilly 50%", 'literal': ':fake 50%'}]
        db.commit()
