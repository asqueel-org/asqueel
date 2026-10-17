"""Offline binding contracts and adapter-independent runtime integration."""
from tests.unit_of_work import completed
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from asqueel.contracts import CompiledQuery, QueryResult
from asqueel.adapters.base import SqlDbAdapter as SqlDbBaseAdapter
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.runtime import PostgresDatabase, Database

# Fake adapter loaded as legacy 'name:module': the database builds SqlDbAdapter(db).
FAKE = 'fake:tests.adapter_driver.test_driver'


def test_formatter_and_execution_profile_are_explicit():
    driver = PostgresAdapter(None)
    driver.validate(CompiledQuery('SELECT %(raw)s', {'raw': 1}))
    for query in (CompiledQuery('x', dialect='sqlite'), CompiledQuery('x', binding='qmark')):
        with pytest.raises(ValueError, match='profile'):
            driver.execute(object(), query)  # No connection methods may run.


class SqlDbAdapter(SqlDbBaseAdapter):
    dialect = 'fake'
    binding = 'fake'

    def __init__(self, dbroot):
        super().__init__(dbroot)
        self.calls = []

    def record(self, name):
        self.calls.append((name, threading.get_ident()))

    def connect(self, conninfo, **kwargs):
        self.record('connect')
        return object()

    def execute(self, connection, query):
        self.record('execute')
        if query.sql == 'fail':
            raise LookupError('original driver error')
        return QueryResult([{'answer': 42}], 1, query.columns)

    def commit(self, connection):
        self.record('commit')

    def rollback(self, connection):
        self.record('rollback')

    def close(self, connection):
        self.record('close')


def test_generic_runtime_injected_driver_affinity_and_original_errors():
    def scenario():
        with Database(implementation=FAKE) as db:
            driver = db.adapter
            result = db.execute(CompiledQuery('ok', dialect='fake', binding='fake'))
            assert result.rows == [{'answer': 42}]
            with pytest.raises(LookupError, match='original driver error'):
                db.execute(CompiledQuery('fail', dialect='fake', binding='fake'))
        assert [name for name, _ in driver.calls] == [
            'connect', 'execute', 'execute', 'rollback', 'close']
        assert len({thread for _, thread in driver.calls}) == 1
        assert driver.calls[0][1] == threading.get_ident()
    scenario()


def test_runtime_rejects_profile_before_connect_or_execute():
    def scenario():
        with Database(implementation=FAKE) as db:
            driver = db.adapter
            with pytest.raises(ValueError, match='profile'):
                db.execute(CompiledQuery('SELECT 1'))
            assert not driver.calls
            with completed(db) as tx:
                with pytest.raises(ValueError, match='profile'):
                    tx.execute(CompiledQuery('SELECT 1'))
                assert not driver.calls
        assert not driver.calls
    scenario()


def test_postgres_facade_uses_the_postgres_adapter():
    with PostgresDatabase() as db:
        assert type(db.adapter) is PostgresAdapter


def test_offline_formatting_and_injected_runtime_do_not_import_psycopg():
    script = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'psycopg' or name.startswith('psycopg.'):
        raise AssertionError('unexpected psycopg dependency')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.runtime import Database, PostgresDatabase
from asqueel.contracts import CompiledQuery, QueryResult
query = PostgresAdapter(None).prepare_sql('SELECT :x', {'x': 3}, {})
assert query.sql == 'SELECT %(x)s'
from asqueel.adapters.base import SqlDbAdapter as SqlDbBaseAdapter
class SqlDbAdapter(SqlDbBaseAdapter):
    dialect = 'fake'
    binding = 'fake'
    def connect(self, *args, **kwargs): return object()
    def execute(self, conn, query): return QueryResult([], 0)
    def commit(self, conn): pass
    def rollback(self, conn): pass
    def close(self, conn): pass
def main():
    with Database(implementation='fake:__main__') as db:
        db.execute(CompiledQuery('x', dialect='fake', binding='fake'))
    with PostgresDatabase():
        pass
main()
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).parents[2],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
