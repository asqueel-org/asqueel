"""A server and its applications own Asqueel databases by name; a call takes and releases them.

The host here is minimal and local to the test: a server with applications by
code, shaped like a kajenn server.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import AsqueelDbMixin, SqlDatabaseConfig


class Server(AsqueelDbMixin):
    def __init__(self):
        super().__init__()
        self.applications = {}

    @property
    def asqueel_owner_name(self):
        return ''

    def asqueel_owner(self, name):
        return self if name == '' else self.applications[name]


class App(AsqueelDbMixin):
    def __init__(self, server, code):
        super().__init__()
        self.server = server
        self.code = code
        server.applications[code] = self

    @property
    def asqueel_owner_name(self):
        return self.code

    def asqueel_owner(self, name):
        return self.server.asqueel_owner(name)


def recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite')
            columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
            columns.column('id', dtype='L')
            columns.column('owner', dtype='T')
    return Recipe


@pytest.fixture
def host(tmp_path):
    server = Server()
    chat = App(server, 'chat')
    plain = App(server, 'plain')
    for owner, name in ((server, 'default'), (server, 'alfadb'), (chat, 'default'), (chat, 'alfadb')):
        db = owner.set_asqueel_db(name, recipe(tmp_path / f'{owner.asqueel_owner_name or "server"}_{name}.db'))
        db.migrate()
        db.table('app.item').insert({'id': 1, 'owner': f'{owner.asqueel_owner_name}:{name}'})
        db.commit()
        db.closeConnection()
    yield server, chat, plain
    for owner in (server, chat, plain):
        for db in owner.asqueel_dbs.values():
            db.close()


def owner_of(db):
    return db.table('app.item').query(columns='$owner').fetch()[0]['owner']


def test_names_with_a_colon_belong_to_an_application(host):
    server, chat, plain = host
    try:
        assert owner_of(chat.get_db('alfadb')) == ':alfadb'
        assert owner_of(chat.get_db('chat:alfadb')) == 'chat:alfadb'
        assert owner_of(plain.get_db('chat:alfadb')) == 'chat:alfadb'
        assert owner_of(chat.db) == 'chat:default'
        assert owner_of(plain.db) == ':default'
        assert owner_of(server.db) == ':default'
    finally:
        chat.release_databases()
        plain.release_databases()
        server.release_databases()


def test_the_first_take_of_a_call_clears_the_context(host):
    _, chat, _ = host
    db = chat.db
    db.updateEnv(user='first call')
    assert chat.db.currentEnv == {'user': 'first call'}
    chat.release_databases()
    assert chat.db.currentEnv == {}
    chat.release_databases()


def test_release_closes_every_database_taken_through_the_owner(host):
    server, chat, _ = host
    taken = [chat.db, chat.get_db('alfadb'), chat.get_db('chat:alfadb')]
    for db in taken:
        owner_of(db)
    assert all(db._connections for db in taken)
    assert chat.taken_databases == taken
    chat.release_databases()
    assert not any(db._connections for db in taken)
    assert chat.taken_databases == []


def test_each_thread_releases_only_its_own_takes(host):
    _, chat, _ = host
    db = chat.db
    db.updateEnv(user='main thread')

    def worker():
        try:
            assert chat.db.currentEnv == {}
            owner_of(chat.db)
            return len(chat.taken_databases)
        finally:
            chat.release_databases()

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(worker).result() == 1
    assert chat.db.currentEnv == {'user': 'main thread'}
    assert chat.taken_databases == [db]
    chat.release_databases()


def test_registration_and_lookup_errors(host, tmp_path):
    server, chat, _ = host
    with pytest.raises(ValueError, match='already registered'):
        chat.set_asqueel_db('alfadb', recipe(tmp_path / 'again.db'))
    with pytest.raises(ValueError, match="has no ':'"):
        chat.set_asqueel_db('x:y', recipe(tmp_path / 'colon.db'))
    with pytest.raises(KeyError, match='no database chat:missing'):
        server.get_db('chat:missing')


def test_a_host_must_name_its_owners():
    class Incomplete(AsqueelDbMixin):
        pass
    with pytest.raises(NotImplementedError, match='asqueel_owner'):
        Incomplete().db


def test_a_host_must_name_itself():
    class Nameless(AsqueelDbMixin):
        def asqueel_owner(self, name):
            return self
    with pytest.raises(NotImplementedError, match='asqueel_owner_name'):
        Nameless().get_db('missing')


def test_release_closes_the_others_and_then_reports_a_failure(host, tmp_path):
    server, chat, _ = host
    extra = chat.set_asqueel_db('extra', recipe(tmp_path / 'extra.db'))
    first, second = chat.get_db('chat:extra'), chat.get_db('chat:alfadb')
    owner_of(second)
    extra.close()
    with pytest.raises(Exception, match='closed'):
        chat.release_databases()
    assert not second._connections
    assert chat.taken_databases == []
    assert first is extra
