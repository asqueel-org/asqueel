"""db.adapter: one adapter object per implementation, loaded as legacy."""
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from tests.unit_of_work import empty_database


@pytest.mark.parametrize(('implementation', 'adapter_class'), [
    ('sqlite', SqliteAdapter), ('postgres', PostgresAdapter), ('postgres3', PostgresAdapter)])
def test_one_adapter_per_implementation(implementation, adapter_class):
    db = empty_database(implementation=implementation)
    try:
        assert db.implementation == implementation
        assert type(db.adapter) is adapter_class
        assert db.adapter.dbroot is db
        assert db.adapter is db.adapter
    finally:
        db.closeConnection()


def test_default_implementation_is_sqlite():
    db = empty_database()
    assert db.implementation == 'sqlite'
    assert type(db.adapter) is SqliteAdapter
    db.closeConnection()
    config = SqlDatabaseConfig()
    config.source.db('demo').packages().package('app').table('item', pkey='id').column('id', dtype='L')
    database = AsqueelDb(config)
    try:
        assert database.config('implementation') == 'sqlite'
        assert type(database.adapter) is SqliteAdapter
    finally:
        database.closeConnection()


def test_postgresql_is_not_an_implementation():
    with pytest.raises(ModuleNotFoundError, match='asqueel.adapters.postgresql'):
        empty_database(implementation='postgresql')


def test_external_module_supplies_the_adapter():
    db = empty_database(implementation='postgres:tests.application_connections.test_connections')
    try:
        assert db.implementation == 'postgres'
        assert type(db.adapter).__module__ == 'tests.application_connections.test_connections'
        assert isinstance(db.adapter, PostgresAdapter)
    finally:
        db.closeConnection()


def test_current_implementation_selects_the_adapter_on_demand():
    db = empty_database(implementation='sqlite').session()
    try:
        main = db.adapter
        assert list(db.adapters) == ['sqlite']
        with db.tempEnv(currentImplementation='postgres'):
            assert type(db.adapter) is PostgresAdapter
            assert db.adapter is db.adapters['postgres']
        assert db.adapter is main
        with db.tempEnv(currentImplementation='postgres'):
            assert db.adapter is db.adapters['postgres']
    finally:
        db.shared.close()


# The 'name:module' form below loads this class: SQLite, from an external module.
class SqlDbAdapter(SqliteAdapter):
    pass


EXTERNAL_SQLITE = 'sqlite:tests.adapters.test_db_adapter'


def test_external_module_is_classified_by_its_implementation_name(tmp_path):
    config = SqlDatabaseConfig()
    db = config.source.db('shop', implementation=EXTERNAL_SQLITE)
    db.connection(name=str(tmp_path / 'shop.db')).options().driver(timeout=5)
    db.packages().package('app').table('item', pkey='id').column('id', dtype='L')
    database = AsqueelDb(config)
    try:
        assert database.implementation == 'sqlite'
        assert type(database.adapter).__module__ == 'tests.adapters.test_db_adapter'
        assert isinstance(database.adapter, SqliteAdapter)
        assert database.model.table('app.item').sqlschema == 'main'
        plan = database.migration_plan()
        assert 'CREATE TABLE' in plan['sql']
    finally:
        database.closeConnection()


def test_external_sqlite_module_keeps_the_sqlite_connection_checks(tmp_path):
    config = SqlDatabaseConfig()
    db = config.source.db('shop', implementation=EXTERNAL_SQLITE)
    db.connection(name=str(tmp_path / 'shop.db'), host='localhost')
    db.packages().package('app').table('item', pkey='id').column('id', dtype='L')
    with pytest.raises(ValueError, match='SQLite uses a filename'):
        AsqueelDb(config)
