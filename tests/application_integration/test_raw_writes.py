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
    """The removed database hooks: the write cycle never calls them."""
    def onWriting(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['db_events'].append(('before', event))
    def onWritten(self, table, event, record, old_record=None, *, raw=False):
        self.currentEnv['db_events'].append(('after', event))


@pytest.fixture(params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
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
                    db = root.db(implementation='postgres', conninfo=postgres_dsn())
                table = db.schemas().schema(schema).tables().table(
                    'item', pkey='id', **({'x_table_class': TableHooks} if table_hooks else {}))
                columns = table.columns()
                columns.column('id', dtype='I')
                columns.column('name', dtype='T')
        db = (SharedHooks if db_hooks else AsqueelDb)(Config)
        db.item = f'{schema}.item'
        databases.append((db, schema))
        if request.param == 'postgres':
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
                if request.param == 'postgres':
                    db.execute(f'DROP SCHEMA "{schema}" CASCADE')
                    db.commit()
            finally:
                db.close()


def rows(table):
    return [dict(row) for row in table.query(order_by='$id').fetch()]


@pytest.mark.parametrize('table_hooks,db_hooks', [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_ordinary_cardinality_and_raw_predicates(make_db, table_hooks, db_hooks, operation):
    db = make_db(table_hooks=table_hooks, db_hooks=db_hooks)
    table = db.table(db.item)
    table.sql_insert([{'id': 1}, {'id': 2}])
    db.commit()
    def raw(where):
        query = table.query(where=where)
        return query.sql_update({'name': 'raw'}) if operation == 'update' else query.sql_delete()
    assert raw('TRUE') == 2
    assert db.currentEnv['table_events'] == db.currentEnv['db_events'] == []
    db.rollback()
    assert rows(table) == [{'id': 1, 'name': 'default'}, {'id': 2, 'name': 'default'}]
    assert raw('$id=99') == 0
    db.rollback()
    if operation == 'update':
        record = {'id': 1, 'name': 'one'}
        assert table.update(record) is record
        assert rows(table) == [{'id': 1, 'name': 'one'}, {'id': 2, 'name': 'default'}]
    else:
        table.delete({'id': 1})
        assert rows(table) == [{'id': 2, 'name': 'default'}]
    assert db.currentEnv['table_events'] == ([operation[0].upper()] if table_hooks else [])
    assert db.currentEnv['db_events'] == []


@pytest.mark.xfail(strict=True, reason='asqueel#17: hooked update/delete of exactly one locked record selected by a where')
@pytest.mark.parametrize('table_hooks', [False, True])
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_ordinary_write_by_where_needs_exactly_one_record(make_db, table_hooks, operation):
    db = make_db(table_hooks=table_hooks)
    table = db.table(db.item)
    table.sql_insert([{'id': 1}, {'id': 2}])
    db.commit()
    for where, error in [('TRUE', RecordMultipleRowsError), ('$id=99', RecordNotFoundError)]:
        with pytest.raises(error):
            if operation == 'update':
                table.update({'name': 'ordinary'}, where=where)
            else:
                table.delete(where=where)
        assert db.currentEnv['table_events'] == []
        with pytest.raises(TransactionStateError):
            db.commit()
        db.rollback()


def test_raw_insert_list_results_defaults_and_no_implicit_commit(make_db):
    db = make_db(table_hooks=True, db_hooks=True)
    table = db.table(db.item)
    records = [{'id': 1, 'name': 'first'}, {'id': 2}]
    original = deepcopy(records)
    assert table.sql_insert(records) is records
    assert records == original
    assert rows(table) == [{'id': 1, 'name': 'first'}, {'id': 2, 'name': 'default'}]
    assert db.currentEnv['table_events'] == db.currentEnv['db_events'] == []
    db.rollback()
    assert table.query().fetch() == []
    table.sql_insert(records)
    db.commit()
    assert len(table.query().fetch()) == 2
    assert table.sql_insert([]) == []
    assert db.currentEnv['db_events'] == []


def test_raw_list_late_sql_failure_rolls_back_entire_pending_work(make_db):
    db = make_db()
    table = db.table(db.item)
    table.insert({'id': 9})
    import sqlite3
    import psycopg
    with pytest.raises((sqlite3.IntegrityError, psycopg.errors.UniqueViolation)):
        table.sql_insert([{'id': 1}, {'id': 1}])
    db.commit()
    assert table.query().fetch() == []


def test_sql_insert_returns_input_and_runs_no_db_hooks(make_db):
    db = make_db(db_hooks=True)
    table = db.table(db.item)
    record = {'id': 1}
    assert table.sql_insert(record) is record
    assert table.sql_update({'id': 1, 'name': 'input'}) is None
    assert rows(table) == [{'id': 1, 'name': 'input'}]
    assert db.currentEnv['db_events'] == []
