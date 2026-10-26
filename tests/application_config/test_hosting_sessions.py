"""asqueel#56: a host hands each call its main SessionDb and closes it at the end of the call."""
import contextvars

import pytest

from asqueel import AsqueelDb, AsqueelDbMixin, SessionDb, SqlDatabaseConfig, TransactionStateError, session


class Server(AsqueelDbMixin):
    @property
    def asqueel_owner_name(self):
        return ''

    def asqueel_owner(self, name):
        return self


def recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db('hosted')
            db.connection(name=str(path), implementation='sqlite')
            item = db.packages().package('app', sqlschema='app', sqlprefix=False).tables().table('item', pkey='id')
            columns = item.columns()
            columns.column('id', dtype='L')
            columns.column('owner', dtype='T')
    return Recipe


@pytest.fixture
def server(tmp_path):
    host = Server()
    shared = host.set_asqueel_db('default', recipe(tmp_path / 'main.db'))
    with shared.session() as setup:
        setup.migrate()
        setup.commit()
    yield host
    shared.close()


def legacy_function(db):
    """Ported genropy code: it receives a db and calls it as a GenroPy db."""
    db.table('app.item').insert({'id': 1, 'owner': 'legacy'})
    db.commit()
    return db.table('app.item').query(columns='$owner').fetch()[0]['owner']


def test_the_host_hands_the_main_session_of_the_call(server):
    db = server.db
    assert isinstance(db, SessionDb)
    assert server.db is db
    assert db is server.asqueel_dbs['default'].session()
    server.release_databases()


def test_ported_code_runs_on_the_session_and_fails_on_the_shared_database(server):
    assert legacy_function(server.db) == 'legacy'
    server.release_databases()
    with pytest.raises(TransactionStateError):
        legacy_function(server.asqueel_dbs['default'])


def test_release_closes_the_sessions_of_the_call(server):
    db = server.db
    db.execute('SELECT 1').close()
    server.release_databases()
    with pytest.raises(TransactionStateError):
        db.execute('SELECT 1')
    fresh = server.db
    assert fresh is not db
    server.release_databases()


def test_each_call_takes_its_own_session(server):
    first = contextvars.Context().run(lambda: server.db)
    second = contextvars.Context().run(lambda: server.db)
    assert first is not second
    first.close()
    second.close()


def test_module_session_is_an_alias_of_db_session(server):
    shared = server.asqueel_dbs['default']
    with session(shared, user='alias') as aliased:
        assert isinstance(aliased, SessionDb)
        assert aliased is shared.session()
        assert aliased.currentEnv['user'] == 'alias'


def test_temp_env_connection_name_selects_the_named_session(server):
    shared = server.asqueel_dbs['default']
    main = shared.session()
    alfa = shared.session('alfa')
    with main.tempEnv(connectionName='alfa'):
        main.table('app.item').insert({'id': 2, 'owner': 'alfa'})
    main.commit()
    assert main.table('app.item').query(columns='$id').fetch() == []
    alfa.commit()
    assert [row['id'] for row in main.table('app.item').query(columns='$id').fetch()] == [2]
    alfa.close()
    main.close()


def test_the_shared_database_is_an_asqueeldb_and_not_a_session(server):
    shared = server.asqueel_dbs['default']
    assert isinstance(shared, AsqueelDb)
    assert not isinstance(shared, SessionDb)
