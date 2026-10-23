from tests.unit_of_work import FakeCursor, completed
import threading


from asqueel.contracts import CompiledQuery
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from tests.unit_of_work import empty_database


# Fake adapter loaded as legacy 'name:module': the database builds SqlDbAdapter(db).
FAKE = 'postgres:tests.environment.test_runtime_environment'


class SqlDbAdapter(PostgresAdapter):
    def __init__(self, dbroot):
        super().__init__(dbroot)
        self.calls = []

    @property
    def environment(self):
        return self.dbroot

    def record(self, method):
        self.calls.append((method, dict(self.environment.environment_snapshot()), threading.get_ident()))

    def connect(self, *args, **kwargs):
        self.record('connect')
        return object()

    def execute(self, connection, query, cursorname=None):
        self.record('execute')
        result = {key: value for key, value in self.environment.environment_snapshot().items()
                  if key not in ('workdate', 'locale')}
        result.update(query.params)
        # A nested adapter scope restores the caller context on normal exit.
        with self.environment.tempEnv(driver_local=True):
            assert self.environment.currentEnv['driver_local']
        return FakeCursor([result])

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
    env = {'company': 1}
    query = CompiledQuery('select', {'env_company': 1}, environment_keys=('company',))
    db = empty_database(implementation=FAKE, environment=env)
    try:
        with db.tempEnv(company=2):
            assert db.execute(query).fetchone()['env_company'] == 2
        assert db.execute(query).fetchone()['env_company'] == 1
    finally:
        db.closeConnection()


def test_runtime_aliases_use_current_context_on_the_calling_thread():
    env = {'company': 1}
    db = empty_database(implementation=FAKE, environment=env)
    try:
        driver = db.adapter
        with db.tempEnv(company=2):
            assert db.currentEnv == {'company': 2}
            with completed(db) as tx:
                with db.tempEnv(company=3):
                    assert [dict(row) for row in tx.execute(CompiledQuery('select')).fetchall()] == [{'company': 3}]
        assert [dict(row) for row in db.execute(CompiledQuery('select')).fetchall()] == [{'company': 1}]
    finally:
        db.closeConnection()
    assert [(method, values['company']) for method, values, _ in driver.calls] == [
        ('connect', 3), ('execute', 3), ('commit', 2),
        ('execute', 1), ('rollback', 1), ('close', 1)]
    assert {thread for _, _, thread in driver.calls} == {threading.get_ident()}
    assert db.currentEnv == {'company': 1}


def test_runtime_default_environments_are_independent():
    first, second = empty_database(implementation='postgres'), empty_database(implementation='postgres')
    with first.tempEnv(company=1):
        assert first.currentEnv == {'company': 1}
        assert second.currentEnv == {}
