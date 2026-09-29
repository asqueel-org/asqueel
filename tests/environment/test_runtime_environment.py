import threading

import pytest

from genro_sql.contracts import (
    CompiledQuery, EnvironmentBinding, EnvironmentMismatchError, QueryResult,
)
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.environment import SqlEnvironment
from genro_sql.query_plan import SqlStatement
from genro_sql.runtime import PostgresDatabase, Database


class ContextDriver:
    dialect = 'postgresql'
    binding = 'psycopg_named'

    def __init__(self, environment):
        self.environment = environment
        self.calls = []

    def validate(self, query):
        PsycopgDriver().validate(query)

    def prepare(self, statement):
        return PsycopgDriver().prepare(statement)

    def record(self, method):
        self.calls.append((method, dict(self.environment.snapshot()), threading.get_ident()))

    def connect(self, *args, **kwargs):
        self.record('connect')
        return object()

    def execute(self, connection, query):
        self.record('execute')
        result = dict(self.environment.snapshot())
        # A nested driver scope restores the caller context on normal exit.
        with self.environment.temp_env(driver_local=True):
            assert self.environment.current_env['driver_local']
        return QueryResult([result], 1)

    def commit(self, connection):
        self.record('commit')

    def rollback(self, connection):
        self.record('rollback')

    def close(self, connection):
        self.record('close')


def test_driver_preparation_preserves_environment_binding():
    binding = EnvironmentBinding(('company',), {'company': 1})
    query = PsycopgDriver().prepare(SqlStatement(('SELECT 1',), environment=binding))
    assert query.environment is binding


def test_stale_environment_rejected_before_connect_and_before_transaction_dispatch():
    env = SqlEnvironment({'company': 1})
    driver = ContextDriver(env)
    query = CompiledQuery('select', environment=EnvironmentBinding(('company',), {'company': 1}))
    with Database(driver=driver, environment=env) as db:
        with db.temp_env(company=2):
            with pytest.raises(EnvironmentMismatchError):
                db.execute(query)
        assert not driver.calls
        with db.transaction() as tx:
            with env.temp_env(company=2):
                with pytest.raises(EnvironmentMismatchError):
                    tx.execute(query)
            assert [method for method, _, _ in driver.calls] == ['connect']
            assert tx.execute(query).rows == [{'company': 1}]


def test_runtime_aliases_use_current_context_on_the_calling_thread():
    env = SqlEnvironment({'company': 1})
    driver = ContextDriver(env)
    with PostgresDatabase(driver=driver, environment=env) as db:
        assert db.environment is env
        with db.tempEnv(company=2):
            assert db.currentEnv == db.current_env == {'company': 2}
            with db.transaction() as tx:
                with db.temp_env(company=3):
                    assert tx.execute(CompiledQuery('select')).rows == [{'company': 3}]
        assert db.execute(CompiledQuery('select')).rows == [{'company': 1}]
    assert [(method, values['company']) for method, values, _ in driver.calls] == [
        ('connect', 2), ('execute', 3), ('commit', 2), ('close', 2),
        ('connect', 1), ('execute', 1), ('commit', 1), ('close', 1)]
    assert {thread for _, _, thread in driver.calls} == {threading.get_ident()}
    assert env.current_env == {'company': 1}


def test_separate_sync_databases_share_explicit_environment_without_leaking_scopes():
    env = SqlEnvironment({'company': 0})
    driver = ContextDriver(env)
    with Database(driver=driver, environment=env) as first, Database(driver=driver, environment=env) as second:
        with first.temp_env(company=1):
            assert second.current_env == {'company': 1}
            first_query = CompiledQuery('select', environment=EnvironmentBinding(('company',), {'company': 1}))
            assert first.execute(first_query).rows == [{'company': 1}]
        with second.temp_env(company=2):
            with pytest.raises(EnvironmentMismatchError):
                second.execute(first_query)
            assert second.execute(CompiledQuery('select')).rows == [{'company': 2}]
        assert env.current_env == {'company': 0}


def test_runtime_default_environments_are_independent():
    with PostgresDatabase() as first, PostgresDatabase() as second:
        assert first.environment is not second.environment
        with first.temp_env(company=1):
            assert first.current_env == {'company': 1}
            assert second.current_env == {}


def test_environment_binding_keeps_private_snapshot_despite_nested_mutations():
    source = {'allowed': [1], 'settings': {'mode': ['visible']}}
    binding = EnvironmentBinding(('allowed', 'settings'), source)
    source['allowed'].append(2)
    snapshot = binding.values
    with pytest.raises(TypeError):
        snapshot['allowed'] = [3]
    snapshot['allowed'].append(4)
    snapshot['settings']['mode'].append('hidden')
    expected = {'allowed': [1], 'settings': {'mode': ['visible']}}
    assert binding.values == expected
    binding.validate(expected)
    with pytest.raises(EnvironmentMismatchError):
        binding.validate(source)
    with pytest.raises(EnvironmentMismatchError):
        binding.validate(snapshot)


def test_environment_binding_distinguishes_missing_key_from_none():
    absent = EnvironmentBinding(('optional',), {})
    absent.validate({})
    with pytest.raises(EnvironmentMismatchError):
        absent.validate({'optional': None})
    present = EnvironmentBinding(('optional',), {'optional': None})
    present.validate({'optional': None})
    with pytest.raises(EnvironmentMismatchError):
        present.validate({})
