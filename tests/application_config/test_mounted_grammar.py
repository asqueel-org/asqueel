"""A host document mounts AsqueelDb.grammar and declares its databases in place.

The host here is a minimal configuration dialect local to the test, shaped like
the ``databases`` section of a kajenn server: an element whose subtree is
governed by the grammar its ``db_class`` carries.
"""
import sqlite3

from genro_builders.builder import element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.configuration import connection_settings
from examples.two_schemas.configure import DatabaseConfiguration


class HostElements:
    @element(sub_tags='databases[0:1]', node_label='configuration')
    def configuration(self): ...

    @element(parent_tags='configuration', sub_tags='database', collection_key='code')
    def databases(self): ...

    @element(parent_tags='databases', _meta={'subbuilder': 'db_class:grammar'})
    def database(self, db_class: type, code: str | None = None): ...


class Host(HostElements, ConfigBuilder):
    pass


def chat_archive(db, path):
    """The database module: one function, called on a mounted or a standalone ``db``."""
    db.connection(name=str(path), implementation='sqlite')
    columns = db.schemas().schema('chat').tables().table('message', pkey='id').columns()
    columns.column('id', dtype='L')
    columns.column('text', dtype='T')


def host_handler(path, *, twice=False):
    class Configuration(Host):
        def main(self, root):
            database = root.configuration().databases().database(db_class=AsqueelDb, code='alfadb')
            chat_archive(database.db(), path)
            if twice:
                database.db()
    return ConfigHandler(Configuration)


def mounted_node(path):
    return host_handler(path).builder.source.get_node('configuration.databases.alfadb.db')


def standalone(path):
    class ChatArchive(SqlDatabaseConfig):
        def main(self, root):
            chat_archive(root.db(), path)
    return ChatArchive


def test_mounted_and_standalone_build_the_same_database(tmp_path):
    path = tmp_path / 'chat.db'
    mounted = AsqueelDb(mounted_node(path))
    recipe = AsqueelDb(standalone(path))
    try:
        assert mounted.model == recipe.model
        assert connection_settings(mounted.config) == connection_settings(recipe.config)
    finally:
        mounted.close()
        recipe.close()


def test_replay_keeps_a_rich_recipe_unchanged(monkeypatch):
    monkeypatch.setenv('PGPASSWORD', 'secret')
    node = ConfigHandler(DatabaseConfiguration).builder.source.get_node('db')
    replayed = AsqueelDb(node)
    original = AsqueelDb(DatabaseConfiguration)
    try:
        assert replayed.model == original.model
        assert connection_settings(replayed.config) == connection_settings(original.config)
    finally:
        replayed.close()
        original.close()


def test_mounted_database_writes_and_reads_on_sqlite(tmp_path):
    path = tmp_path / 'chat.db'
    connection = sqlite3.connect(tmp_path / 'chat_chat.db')
    connection.execute('create table message(id integer primary key, text text)')
    connection.commit()
    connection.close()
    db = AsqueelDb(mounted_node(path))
    try:
        db.table('chat.message').insert({'text': 'ciao'})
        db.commit()
        assert db.table('chat.message').query(columns='$id, $text').fetch() == [{'id': 1, 'text': 'ciao'}]
    finally:
        db.close()


def test_a_second_db_under_the_same_host_node_is_refused(tmp_path):
    with pytest.raises(ValueError, match='already present'):
        host_handler(tmp_path / 'chat.db', twice=True)


def test_a_mounted_database_starts_at_db(tmp_path):
    source = host_handler(tmp_path / 'chat.db').builder.source
    schemas = source.get_node('configuration.databases.alfadb.db.schemas')
    with pytest.raises(TypeError, match="starts at a 'db' node"):
        AsqueelDb(schemas)
