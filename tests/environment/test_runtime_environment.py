from tests.unit_of_work import completed
import threading


from asqueel.contracts import CompiledQuery, QueryResult
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.environment import SqlEnvironment
from asqueel.runtime import PostgresDatabase, Database


# Fake adapter loaded as legacy 'name:module': the database builds SqlDbAdapter(db).
FAKE = 'postgres:tests.environment.test_runtime_environment'


class SqlDbAdapter(PostgresAdapter):
    def __init__(self, dbroot):
        super().__init__(dbroot)
        self.calls = []

    @property
    def environment(self):
        return self.dbroot.environment

    def record(self, method):
        self.calls.append((method, dict(self.environment.snapshot()), threading.get_ident()))

    def connect(self, *args, **kwargs):
        self.record('connect')
        return object()

    def execute(self, connection, query):
        self.record('execute')
        result = dict(self.environment.snapshot())
        result.update(query.params)
        # A nested adapter scope restores the caller context on normal exit.
        with self.environment.temp_env(driver_local=True):
            assert self.environment.current_env['driver_local']
        return QueryResult([result], 1)

    def commit(self, connection):
        self.record('commit')

    def rollback(self, connection):
        self.record('rollback')

    def close(self, connection):
        self.record('close')


def test_driver_preparation_collects_environment_keys():
    query = PostgresAdapter(None).prepare_sql('SELECT :env_company', {}, {'company': 1})
    assert query.environment_keys == ('company',)
    assert query.params == {'env_company': 1}


def test_reused_query_reads_the_environment_of_every_execution():
    env = SqlEnvironment({'company': 1})
    query = CompiledQuery('select', {'env_company': 1}, environment_keys=('company',))
    db = Database(implementation=FAKE, environment=env)
    try:
        with db.temp_env(company=2):
            assert db.execute(query).rows[0]['env_company'] == 2
        assert db.execute(query).rows[0]['env_company'] == 1
    finally:
        db.closeConnection()


def test_runtime_aliases_use_current_context_on_the_calling_thread():
    env = SqlEnvironment({'company': 1})
    db = Database(implementation=FAKE, environment=env)
    try:
        driver = db.adapter
        assert db.environment is env
        with db.tempEnv(company=2):
            assert db.currentEnv == db.current_env == {'company': 2}
            with completed(db) as tx:
                with db.temp_env(company=3):
                    assert tx.execute(CompiledQuery('select')).rows == [{'company': 3}]
        assert db.execute(CompiledQuery('select')).rows == [{'company': 1}]
    finally:
        db.closeConnection()
    assert [(method, values['company']) for method, values, _ in driver.calls] == [
        ('connect', 3), ('execute', 3), ('commit', 2),
        ('execute', 1), ('rollback', 1), ('close', 1)]
    assert {thread for _, _, thread in driver.calls} == {threading.get_ident()}
    assert env.current_env == {'company': 1}


def test_separate_sync_databases_share_explicit_environment_without_leaking_scopes():
    env = SqlEnvironment({'company': 0})
    first, second = Database(implementation=FAKE, environment=env), Database(implementation=FAKE, environment=env)
    try:
        with first.temp_env(company=1):
            assert second.current_env == {'company': 1}
            first_query = CompiledQuery('select', {'env_company': 1}, environment_keys=('company',))
            assert first.execute(first_query).rows == [{'company': 1, 'env_company': 1}]
        with second.temp_env(company=2):
            assert second.execute(first_query).rows[0]['env_company'] == 2
            assert second.execute(CompiledQuery('select')).rows == [{'company': 2}]
        assert env.current_env == {'company': 0}
    finally:
        first.closeConnection()
        second.closeConnection()


def test_runtime_default_environments_are_independent():
    first, second = PostgresDatabase(), PostgresDatabase()
    assert first.environment is not second.environment
    with first.temp_env(company=1):
        assert first.current_env == {'company': 1}
        assert second.current_env == {}
