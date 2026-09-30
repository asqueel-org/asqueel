"""Offline binding contracts and driver-independent runtime integration."""
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from asqueel.contracts import CompiledQuery, QueryResult, ResultColumn
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.query_plan import Identifier, Parameter, SqlStatement
from asqueel.runtime import PostgresDatabase, Database


def test_formatter_preserves_literal_percent_and_structural_parameter_boundaries():
    column = ResultColumn('result', 'T')
    statement = SqlStatement((
        'SELECT \'50% and %(literal)s\', 8 % 3, "percent%name", ',
        Parameter('value'), ', ', Parameter('value'), ' -- 10%\n',
    ), {'value': "O'Reilly", 'unused': 99}, (column,))
    query = PsycopgDriver().prepare(statement)
    assert query.sql == 'SELECT \'50%% and %%(literal)s\', 8 %% 3, "percent%%name", %(value)s, %(value)s -- 10%%\n'
    assert dict(query.params) == {'value': "O'Reilly"}
    assert query.columns == (column,)
    assert (query.dialect, query.binding) == ('postgresql', 'psycopg_named')
    assert "O'Reilly" not in query.sql
    assert PsycopgDriver().prepare(statement) == query


@pytest.mark.parametrize('parts,params,error', [
    ((Parameter('missing'),), {}, ValueError),
    ((Parameter('bad)name'),), {'bad)name': 1}, ValueError),
    ((Parameter('1name'),), {'1name': 1}, ValueError),
    ((Parameter('é'),), {'é': 1}, ValueError),
    ((Identifier('unquoted'),), {}, TypeError),
    ((object(),), {}, TypeError),
])
def test_formatter_rejects_invalid_parts_or_parameters(parts, params, error):
    with pytest.raises(error):
        PsycopgDriver().prepare(SqlStatement(parts, params))


def test_formatter_and_execution_profile_are_explicit():
    driver = PsycopgDriver()
    with pytest.raises(ValueError, match='dialect'):
        driver.prepare(SqlStatement(('SELECT 1',), dialect='sqlite'))
    with pytest.raises(TypeError):
        driver.prepare(CompiledQuery('SELECT 1'))
    driver.validate(CompiledQuery('SELECT %(raw)s', {'raw': 1}))
    for query in (CompiledQuery('x', dialect='sqlite'), CompiledQuery('x', binding='qmark')):
        with pytest.raises(ValueError, match='profile'):
            driver.execute(object(), query)  # No connection methods may run.


class RecordingDriver:
    dialect = 'fake'
    binding = 'fake'

    def __init__(self):
        self.calls = []

    def validate(self, query):
        if not isinstance(query, CompiledQuery):
            raise TypeError('query required')
        if (query.dialect, query.binding) != (self.dialect, self.binding):
            raise ValueError('profile mismatch')

    def record(self, name):
        self.calls.append((name, threading.get_ident()))

    def prepare(self, statement):
        raise NotImplementedError

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
        driver = RecordingDriver()
        with Database(driver=driver) as db:
            result = db.execute(CompiledQuery('ok', dialect='fake', binding='fake'))
            assert result.rows == [{'answer': 42}]
            with pytest.raises(LookupError, match='original driver error'):
                db.execute(CompiledQuery('fail', dialect='fake', binding='fake'))
        assert [name for name, _ in driver.calls] == [
            'connect', 'execute', 'commit', 'close', 'connect', 'execute', 'rollback', 'close']
        assert len({thread for _, thread in driver.calls}) == 1
        assert driver.calls[0][1] == threading.get_ident()
    scenario()


def test_runtime_rejects_profile_before_connect_or_execute():
    def scenario():
        driver = RecordingDriver()
        with Database(driver=driver) as db:
            with pytest.raises(ValueError, match='profile'):
                db.execute(CompiledQuery('SELECT 1'))
            assert not driver.calls
            with db.transaction() as tx:
                with pytest.raises(ValueError, match='profile'):
                    tx.execute(CompiledQuery('SELECT 1'))
                assert [name for name, _ in driver.calls] == ['connect']
        assert [name for name, _ in driver.calls] == ['connect', 'commit', 'close']
    scenario()


def test_postgres_facade_rejects_other_profiles():
    with pytest.raises(ValueError, match='profile'):
        PostgresDatabase(driver=RecordingDriver())


def test_offline_formatting_and_injected_runtime_do_not_import_psycopg():
    script = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'psycopg' or name.startswith('psycopg.'):
        raise AssertionError('unexpected psycopg dependency')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.query_plan import SqlStatement, Parameter
from asqueel.runtime import Database, PostgresDatabase
from asqueel.contracts import CompiledQuery, QueryResult
query = PsycopgDriver().prepare(SqlStatement(('SELECT ', Parameter('x')), {'x': 3}))
assert query.sql == 'SELECT %(x)s'
class Driver:
    dialect = 'fake'
    binding = 'fake'
    def validate(self, query): pass
    def connect(self, *args, **kwargs): return object()
    def execute(self, conn, query): return QueryResult([], 0)
    def commit(self, conn): pass
    def rollback(self, conn): pass
    def close(self, conn): pass
def main():
    with Database(driver=Driver()) as db:
        db.execute(CompiledQuery('x', dialect='fake', binding='fake'))
    with PostgresDatabase():
        pass
main()
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).parents[2],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
