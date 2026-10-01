"""Record cardinality is independent of hooks; raw writes share one unit of work."""
from copy import deepcopy
from uuid import uuid4

import pytest

from asqueel import (
    AsqueelDb, RecordMultipleRowsError, RecordNotFoundError,
    SqlDatabaseConfig, SqlTable, TransactionStateError,
)
from tests.native_support import postgres_dsn


class TableHooks(SqlTable):
    def trigger_onInserting(self, record):
        self.db.currentEnv['table_events'].append('I')
    def trigger_onUpdating(self, record, old_record=None):
        self.db.currentEnv['table_events'].append('U')
    def trigger_onDeleting(self, record):
        self.db.currentEnv['table_events'].append('D')


class SharedHooks(AsqueelDb):
    def onWriting(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['db_events'].append(('before', event, deepcopy(record), old_record, raw))
        if event == 'U' and self.currentEnv.get('change_name'):
            record['name'] = 'hook value'
    def onWritten(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['db_events'].append(('after', event, deepcopy(record), old_record, raw))
        if event == 'I' and record['id'] == self.currentEnv.get('fail_id'):
            raise ValueError('late shared hook failure')


@pytest.fixture(params=['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)])
def make_db(request, tmp_path):
    databases = []
    def make(*, table_hooks=False, db_hooks=False):
        schema = 'raw_' + uuid4().hex[:12]
        class Config(SqlDatabaseConfig):
            def main(self, root):
                if request.param == 'sqlite':
                    db = root.db(implementation='sqlite')
                    db.connection(name=str(tmp_path / f'{schema}.db'))
                else:
                    db = root.db(conninfo=postgres_dsn())
                table = db.schemas().schema(schema).tables().table(
                    'item', pkey='id', **({'x_table_class': TableHooks} if table_hooks else {}))
                columns = table.columns()
                columns.column('id', dtype='I')
                columns.column('name', dtype='T')
        db = (SharedHooks if db_hooks else AsqueelDb)(Config)
        databases.append((db, schema))
        if request.param == 'postgresql':
            db.execute(f'CREATE SCHEMA "{schema}"')
        db.execute(f'CREATE TABLE "{schema}".item (id INTEGER PRIMARY KEY, name TEXT DEFAULT \'default\')')
        db.commit()
        db.updateEnv(table_events=[], db_events=[])
        return db
    try:
        yield make
    finally:
        for db, schema in databases:
            try:
                db.rollback()
                if request.param == 'postgresql':
                    db.execute(f'DROP SCHEMA "{schema}" CASCADE')
                    db.commit()
            finally:
                db.close()


@pytest.mark.parametrize('table_hooks,db_hooks', [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_ordinary_cardinality_and_raw_predicates(make_db, table_hooks, db_hooks, operation):
    db = make_db(table_hooks=table_hooks, db_hooks=db_hooks)
    table = db.table('item')
    table.raw_insert([{'id': 1}, {'id': 2}])
    db.commit()
    db.currentEnv['db_events'].clear()
    for where, error in [('TRUE', RecordMultipleRowsError), ('$id=99', RecordNotFoundError)]:
        with pytest.raises(error):
            if operation == 'update':
                table.update({'name': 'ordinary'}, where=where)
            else:
                table.delete(where=where)
        assert db.currentEnv['table_events'] == db.currentEnv['db_events'] == []
        with pytest.raises(TransactionStateError):
            db.commit()
        db.rollback()
    raw = getattr(table, 'raw_' + operation)
    result = raw({'name': 'raw'}, where='TRUE') if operation == 'update' else raw(where='TRUE')
    assert result.rowcount == 2
    assert len(result.rows) == 2
    assert db.currentEnv['table_events'] == []
    if db_hooks:
        before, after = db.currentEnv['db_events']
        assert before[2] == ({'name': 'raw'} if operation == 'update' else None)
        assert before[3:] == after[3:] == (None, True)
    db.rollback()
    assert table.query(order_by='$id').fetch() == [{'id': 1, 'name': 'default'}, {'id': 2, 'name': 'default'}]
    result = raw({'name': 'raw'}, where='$id=99') if operation == 'update' else raw(where='$id=99')
    assert result.rowcount == 0
    db.rollback()
    ordinary = getattr(table, operation)
    result = ordinary({'id': 1, 'name': 'one'}) if operation == 'update' else ordinary(1)
    assert result.rowcount == 1
    assert db.currentEnv['table_events'] == ([operation[0].upper()] if table_hooks else [])


def test_raw_insert_list_results_defaults_and_no_implicit_commit(make_db):
    db = make_db(table_hooks=True, db_hooks=True)
    records = [{'id': 1, 'name': 'first'}, {'id': 2}]
    original = deepcopy(records)
    result = db.raw_insert('item', records)
    assert result.rows == [{'id': 1, 'name': 'first'}, {'id': 2, 'name': 'default'}]
    assert result.rowcount == 2 and [c.name for c in result.columns] == ['id', 'name']
    assert records == original
    assert db.currentEnv['table_events'] == []
    assert len(db.currentEnv['db_events']) == 4
    db.rollback()
    assert db.table('item').query().fetch() == []
    result = db.table('item').raw_insert(records, returning=None)
    assert result.rows == [] and result.rowcount == 2 and result.columns == ()
    db.commit()
    assert len(db.table('item').query().fetch()) == 2
    db.currentEnv['db_events'].clear()
    result = db.table('item').raw_insert([])
    assert result.rowcount == 0 and result.rows == [] and result.columns == ()
    assert db.currentEnv['db_events'] == []


def test_raw_list_late_python_failure_requires_rollback(make_db):
    db = make_db(db_hooks=True)
    db.currentEnv['fail_id'] = 2
    with pytest.raises(ValueError, match='late shared'):
        db.table('item').raw_insert([{'id': 1}, {'id': 2}])
    with pytest.raises(TransactionStateError):
        db.commit()
    db.rollback()
    assert db.table('item').query().fetch() == []


def test_raw_list_late_sql_failure_rolls_back_entire_pending_work(make_db):
    db = make_db()
    table = db.table('item')
    table.insert({'id': 9})
    import sqlite3
    import psycopg
    with pytest.raises((sqlite3.IntegrityError, psycopg.errors.UniqueViolation)):
        table.raw_insert([{'id': 1}, {'id': 1}])
    db.commit()
    assert table.query().fetch() == []


def test_raw_insert_input_contract_and_hook_mutation(make_db):
    db = make_db(db_hooks=True)
    table = db.table('item')
    for method, value in [(table.insert, [{'id': 1}]), (table.raw_insert, [{'id': 1}, 2])]:
        with pytest.raises(TypeError):
            method(value)
        assert db.currentEnv['db_events'] == []
        db.rollback()
        assert table.query().fetch() == []
    table.raw_insert({'id': 1})
    db.currentEnv['change_name'] = True
    assert table.raw_update({'name': 'input'}, where='TRUE').rows[0]['name'] == 'hook value'
